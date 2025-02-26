#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

import argparse
import os
import subprocess
import sys
from contextlib import asynccontextmanager
import time

import aiohttp
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from dotenv import load_dotenv
from loguru import logger
import http.client as http_client
import logging

from pipecat.transports.services.helpers.daily_rest import DailyRESTHelper, DailyRoomParams, DailyRoomProperties

MAX_BOTS_PER_ROOM = 1

# Bot sub-process dict for status reporting and concurrency control
bot_procs = {}

# Dictionary to store bot type by room URL
room_bot_types = {}

daily_helpers = {}

load_dotenv(override=True)

# Remove existing logger handlers and set up new configuration
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="DEBUG"
)

http_client.HTTPConnection.debuglevel = 1
logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)
requests_log = logging.getLogger("urllib3")
requests_log.setLevel(logging.DEBUG)
requests_log.propagate = True


def cleanup():
    # Clean up function, just to be extra safe
    for entry in bot_procs.values():
        proc = entry[0]
        proc.terminate()
        proc.wait()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting application...")
    aiohttp_session = aiohttp.ClientSession()
    
    daily_api_key = os.getenv("DAILY_API_KEY", "").strip()
    if not daily_api_key:
        logger.error("No Daily API key found")
        raise Exception("DAILY_API_KEY environment variable is required")

    logger.debug(f"Initializing Daily REST helper with API key: {daily_api_key[:6]}...{daily_api_key[-4:]}")
    
    daily_helpers["rest"] = DailyRESTHelper(
        daily_api_key=daily_api_key,
        daily_api_url="https://api.daily.co/v1",
        aiohttp_session=aiohttp_session,
    )
    logger.info("Application startup complete")
    yield
    logger.info("Shutting down application...")
    await aiohttp_session.close()
    cleanup()
    logger.info("Application shutdown complete")


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "Bot server is running"}


@app.post("/start_bot")
async def start_bot(request: Request):
    try:
        # Get raw request body first
        raw_body = await request.body()
        logger.info(f"Raw request body: {raw_body.decode()}")
        
        # Get request data
        data = await request.json()
        
        # Enhanced request logging
        logger.info("=== Incoming Request Details ===")
        logger.info(f"Headers: {dict(request.headers)}")
        logger.info(f"Method: {request.method}")
        logger.info(f"Raw JSON data: {data}")
        logger.info(f"botType in request: {'botType' in data}")
        if 'botType' in data:
            logger.info(f"botType value: {data['botType']}")
            logger.info(f"botType type: {type(data['botType'])}")
        logger.info("==============================")
        
        bot_type = data.get("botType", "intake")  # Default to intake bot
        
        # Get the Daily API key from environment
        daily_api_key = os.getenv("DAILY_API_KEY")
        daily_room_url = os.getenv("DAILY_SAMPLE_ROOM_URL")
        
        logger.debug(f"Using Daily API key: {daily_api_key[:6]}...{daily_api_key[-4:]}")
        logger.debug(f"Using room URL: {daily_room_url}")
        
        if not daily_api_key:
            logger.error("DAILY_API_KEY environment variable is not set")
            raise HTTPException(
                status_code=500, 
                detail="DAILY_API_KEY environment variable is not set"
            )

        if not daily_room_url:
            logger.error("DAILY_SAMPLE_ROOM_URL environment variable is not set")
            raise HTTPException(
                status_code=500,
                detail="DAILY_SAMPLE_ROOM_URL environment variable is not set"
            )

        # Get a token for the existing room
        logger.info("Attempting to get room token...")
        try:
            token = await daily_helpers["rest"].get_token(daily_room_url)
            logger.debug(f"Token received: {token[:10]}...")  # Log partial token for security
        except Exception as e:
            logger.error(f"Failed to get room token: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate room token: {str(e)}"
            )

        if not token:
            logger.error("Token generation succeeded but no token was returned")
            raise HTTPException(
                status_code=500,
                detail="Failed to generate room token - no token returned"
            )

        # Set these as environment variables for the bot process
        env = os.environ.copy()
        env["DAILY_SAMPLE_ROOM_URL"] = daily_room_url  # Use the existing room URL
        env["DAILY_API_KEY"] = daily_api_key
        env["DAILY_ROOM_TOKEN"] = token

        logger.info(f"Starting {bot_type} bot process...")
        # Create a new bot process with the updated environment
        try:
            # Select the appropriate bot script based on type
            if bot_type == "movie":
                bot_script = "movie_bot.py"
            elif bot_type == "shawarma":
                bot_script = "shawarma_bot.py"
            elif bot_type == "simple":
                bot_script = "simple.py"
            else:
                bot_script = "bot.py"
            
            proc = subprocess.Popen(
                [sys.executable, bot_script],
                env=env,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            logger.info(f"Bot process started with PID: {proc.pid}")
        except Exception as e:
            logger.error(f"Failed to start bot process: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to start bot: {str(e)}"
            )
        
        # Store the process info
        bot_procs[proc.pid] = (proc, daily_room_url)
        
        return {
            "status": "success", 
            "message": "Bot started",
            "room_url": daily_room_url,
            "pid": proc.pid
        }
    except Exception as e:
        logger.error(f"Unexpected error in start_bot: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/start_agent")
async def start_agent(request: Request):
    print(f"!!! Creating room")
    room = await daily_helpers["rest"].create_room(DailyRoomParams())
    print(f"!!! Room URL: {room.url}")
    # Ensure the room property is present
    if not room.url:
        raise HTTPException(
            status_code=500,
            detail="Missing 'room' property in request data. Cannot start agent without a target room!",
        )

    # Check if there is already an existing process running in this room
    num_bots_in_room = sum(
        1 for proc in bot_procs.values() if proc[1] == room.url and proc[0].poll() is None
    )
    if num_bots_in_room >= MAX_BOTS_PER_ROOM:
        raise HTTPException(status_code=500, detail=f"Max bot limited reach for room: {room.url}")

    # Get the token for the room
    token = await daily_helpers["rest"].get_token(room.url)

    if not token:
        raise HTTPException(status_code=500, detail=f"Failed to get token for room: {room.url}")

    # Spawn a new agent, and join the user session
    # Note: this is mostly for demonstration purposes (refer to 'deployment' in README)
    try:
        proc = subprocess.Popen(
            [f"python3 -m bot -u {room.url} -t {token}"],
            shell=True,
            bufsize=1,
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )
        bot_procs[proc.pid] = (proc, room.url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start subprocess: {e}")

    return RedirectResponse(room.url)


@app.get("/status/{pid}")
def get_status(pid: int):
    # Look up the subprocess
    proc = bot_procs.get(pid)

    # If the subprocess doesn't exist, return an error
    if not proc:
        raise HTTPException(status_code=404, detail=f"Bot with process id: {pid} not found")

    # Check the status of the subprocess
    if proc[0].poll() is None:
        status = "running"
    else:
        status = "finished"

    return JSONResponse({"bot_id": pid, "status": status})


@app.post("/connect")
async def rtvi_connect(request: Request):
    """RTVI connect endpoint that creates a room and returns connection credentials."""
    try:
        # Get raw request body first
        raw_body = await request.body()
        logger.info(f"Raw request body: {raw_body.decode()}")
        
        # Get request data
        data = await request.json()
        
        # Enhanced request logging
        logger.info("=== Incoming Request Details ===")
        logger.info(f"Headers: {dict(request.headers)}")
        logger.info(f"Method: {request.method}")
        logger.info(f"Raw JSON data: {data}")
        logger.info(f"botType in request: {'botType' in data}")
        
        # Extract botType from request or get from stored room type
        if 'botType' in data:
            bot_type = data["botType"].lower()
            logger.info(f"Using botType from request: {bot_type}")
        else:
            # Try to get bot type from room URL if this is a reconnection
            daily_room_url = data.get("room_url")
            bot_type = room_bot_types.get(daily_room_url, "intake")
            logger.info(f"Using stored botType: {bot_type}")
        
        logger.info("==============================")
        
        logger.info(f"=== Starting new connection request ===")
        logger.info(f"Final bot type being used: {bot_type}")
        
        # Get the Daily API key from environment
        daily_api_key = os.getenv("DAILY_API_KEY")
        if not daily_api_key:
            logger.error("DAILY_API_KEY environment variable is not set")
            raise HTTPException(
                status_code=500, 
                detail="DAILY_API_KEY environment variable is not set"
            )

        # Create a new room with expiry time
        try:
            # Define room expiry time (e.g., 30 minutes)
            ROOM_EXPIRY_TIME = 10 * 60  # 10 minutes in seconds
            
            # Create room properties with expiry time
            room_properties = DailyRoomProperties(
                exp=time.time() + ROOM_EXPIRY_TIME,  # Room expires in 10 minutes
                start_audio_off=False,
                start_video_off=True,
                eject_at_room_exp=True,  # Eject participants when room expires
                enable_prejoin_ui=False  #  Skip the prejoin UI
            )
            
            # Create room parameters with properties
            room_params = DailyRoomParams(
                privacy="public",
                properties=room_properties
            )
            
            # Create the room
            room = await daily_helpers["rest"].create_room(room_params)
            daily_room_url = room.url
            logger.info(f"Created room: {daily_room_url} with expiry in {ROOM_EXPIRY_TIME/60} minutes")
            
            # Store the bot type for this room
            room_bot_types[daily_room_url] = bot_type
            
        except Exception as e:
            logger.error(f"Failed to create room: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create room: {str(e)}"
            )

        # Get a token for the room
        logger.info("Attempting to get room token...")
        try:
            token = await daily_helpers["rest"].get_token(daily_room_url)
            logger.debug(f"Token received: {token[:10]}...")
        except Exception as e:
            logger.error(f"Failed to get room token: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate room token: {str(e)}"
            )

        if not token:
            logger.error("Token generation succeeded but no token was returned")
            raise HTTPException(
                status_code=500,
                detail="Failed to generate room token - no token returned"
            )

        # Set these as environment variables for the bot process
        env = os.environ.copy()
        env["DAILY_ROOM_URL"] = daily_room_url
        env["DAILY_API_KEY"] = daily_api_key
        env["DAILY_ROOM_TOKEN"] = token

        logger.info(f"=== Starting bot process ===")
        logger.info(f"Bot type: {bot_type}")
        logger.info(f"Room URL: {daily_room_url}")
        
        # Create a new bot process with the updated environment
        try:
            # Select the appropriate bot script based on type
            if bot_type == "movie":
                bot_script = "movie_bot.py"
            elif bot_type == "shawarma":
                bot_script = "shawarma_bot.py"
            elif bot_type == "simple":
                bot_script = "simple.py"
            else:
                bot_script = "bot.py"
                
            logger.info(f"Selected bot script: {bot_script}")
            
            proc = subprocess.Popen(
                [sys.executable, bot_script],
                env=env,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            logger.info(f"Bot process started successfully with PID: {proc.pid}")
        except Exception as e:
            logger.error(f"Failed to start bot process: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to start bot: {str(e)}"
            )
        
        # Store the process info
        bot_procs[proc.pid] = (proc, daily_room_url)
        
        # Return the authentication bundle in format expected by DailyTransport
        response_data = {
            "room_url": daily_room_url,
            "token": token
        }
        logger.info(f"Returning connection data for room: {daily_room_url}")
        return response_data

    except Exception as e:
        logger.error(f"Unexpected error in rtvi_connect: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    default_host = os.getenv("HOST", "0.0.0.0")
    default_port = int(os.getenv("FAST_API_PORT", "7860"))

    parser = argparse.ArgumentParser(description="Daily patient-intake FastAPI server")
    parser.add_argument("--host", type=str, default=default_host, help="Host address")
    parser.add_argument("--port", type=int, default=default_port, help="Port number")
    parser.add_argument("--reload", action="store_true", help="Reload code on change")

    config = parser.parse_args()
    print(f"to join a test room, visit http://localhost:{config.port}/")
    uvicorn.run(
        "server:app",
        host=config.host,
        port=config.port,
        reload=config.reload,
    )
