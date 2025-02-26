#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

import asyncio
import os
import sys
from typing import List, Literal, TypedDict, Union, Dict, Optional

from dotenv import load_dotenv
from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.processors.transcript_processor import TranscriptProcessor
from pipecat.processors.frameworks.rtvi import (
    RTVISpeakingProcessor,
    RTVIUserTranscriptionProcessor,
    RTVIBotTranscriptionProcessor,
    RTVIBotLLMProcessor,
    RTVIBotTTSProcessor,
    RTVIMetricsProcessor,
    FrameDirection,
)
from pipecat.services.azure import AzureSTTService
from deepgram import LiveOptions
from pipecat.services.elevenlabs import ElevenLabsTTSService
from pipecat.services.openai import OpenAILLMService
from pipecat.transports.services.daily import DailyParams, DailyTransport
from pipecat_flows import FlowArgs, FlowConfig, FlowManager, FlowResult, ContextStrategy, ContextStrategyConfig
from pipecat.transcriptions.language import Language
from pipecat.frames.frames import EndFrame


load_dotenv(override=True)

logger.remove(0)
logger.add(sys.stderr, level="DEBUG")

# Shawarma menu with prices
SHAWARMA_MENU = {
    "chicken": {
        "name": "شاورما فراخ",
        "price": 65,
        "description": "شاورما دجاج مشوية على الفحم مع صوص طحينة وخضار",
    },
    "meat": {
        "name": "شاورما لحمة",
        "price": 85,
        "description": "شاورما لحم بقري مشوي على الفحم مع صوص طحينة وخضار",
    },
    "mix": {
        "name": "شاورما مكس",
        "price": 75,
        "description": "شاورما مشكلة (لحم ودجاج) مع صوص طحينة وخضار",
    },
}

# Extras options
EXTRAS = {
    "fries": {"name": "بطاطس", "price": 25},
    "cheese": {"name": "جبنة إضافية", "price": 10},
    "garlic_sauce": {"name": "صوص ثوم", "price": 5},
    "tahini_extra": {"name": "صوص طحينة إضافي", "price": 5},
}


# Type definitions for the order
class MenuItem(TypedDict):
    name: str
    price: int
    description: str


class ExtraItem(TypedDict):
    name: str
    price: int


class OrderItem(TypedDict):
    type: str
    quantity: int
    extras: List[str]
    price: int


class Order(TypedDict):
    items: List[OrderItem]
    address: str
    phone: str
    total: int
    special_instructions: Optional[str]
    delivery_notes: Optional[str]


class MenuResult(FlowResult):
    menu: Dict[str, MenuItem]


class ExtrasResult(FlowResult):
    extras: Dict[str, ExtraItem]


class OrderResult(FlowResult):
    item: OrderItem
    price: int


class OrderDetailsResult(FlowResult):
    address: str
    phone: str
    special_instructions: Optional[str]
    estimated_time: int


class OrderConfirmationResult(FlowResult):
    order: Order
    estimated_time: int  # in minutes
    order_summary: str  # Human-readable summary


class ErrorResult(FlowResult):
    status: Literal["error"]
    error: str


# Order management system
class OrderManager:
    """Handles all order operations with proper typing and error handling."""

    def __init__(self):
        self.current_order: Optional[Order] = None
        self.next_order_id = 1

    def create_new_order(self) -> Order:
        """Creates a new empty order."""
        self.current_order = {
            "items": [], 
            "address": "", 
            "phone": "", 
            "total": 0,
            "special_instructions": None,
            "delivery_notes": None
        }
        return self.current_order

    def add_item(
        self, item_type: str, quantity: int, extras: List[str] = None
    ) -> OrderItem:
        """Add an item to the current order."""
        if not self.current_order:
            self.create_new_order()

        if extras is None:
            extras = []

        if item_type not in SHAWARMA_MENU:
            raise ValueError(f"Invalid item type: {item_type}")

        new_item = {"type": item_type, "quantity": quantity, "extras": extras}

        self.current_order["items"].append(new_item)
        self._update_total()

        return new_item

    def calculate_item_price(self, item: OrderItem) -> int:
        """Calculate the price of an order item including extras."""
        base_price = SHAWARMA_MENU[item["type"]]["price"] * item["quantity"]
        extras_price = sum(
            EXTRAS[extra]["price"] for extra in item["extras"] if extra in EXTRAS
        )
        return base_price + extras_price

    def _update_total(self) -> int:
        """Update the total price of the order."""
        if not self.current_order:
            return 0

        total = 0
        for item in self.current_order["items"]:
            total += self.calculate_item_price(item)

        self.current_order["total"] = total
        return total

    def set_delivery_info(self, address: str, phone: str, special_instructions: str = None) -> Order:
        """Set delivery information for the current order."""
        if not self.current_order:
            raise ValueError("No active order")

        self.current_order["address"] = address
        self.current_order["phone"] = phone
        
        if special_instructions:
            self.current_order["special_instructions"] = special_instructions

        return self.current_order
    
    def add_delivery_notes(self, notes: str) -> Order:
        """Add delivery notes to the current order."""
        if not self.current_order:
            raise ValueError("No active order")
            
        self.current_order["delivery_notes"] = notes
        return self.current_order

    def get_estimated_delivery_time(self) -> int:
        """Calculate estimated delivery time in minutes."""
        # Simple estimation: 15 minutes base + 5 minutes per item
        if not self.current_order or not self.current_order["items"]:
            return 30  # Default time

        return 15 + (5 * sum(item["quantity"] for item in self.current_order["items"]))
    
    def get_order_summary(self) -> str:
        """Generate a human-readable summary of the order."""
        if not self.current_order or not self.current_order["items"]:
            return "لا يوجد طلب حالي"
            
        summary_parts = []
        
        # Add items
        for item in self.current_order["items"]:
            item_type = item["type"]
            quantity = item["quantity"]
            extras = item["extras"]
            
            item_name = SHAWARMA_MENU[item_type]["name"]
            item_price = self.calculate_item_price(item)
            
            item_summary = f"{item_name} عدد {quantity}"
            
            if extras:
                extras_names = [EXTRAS[extra]["name"] for extra in extras]
                item_summary += f" مع {', '.join(extras_names)}"
                
            item_summary += f" - {item_price} جنيه"
            summary_parts.append(item_summary)
            
        # Add total
        summary_parts.append(f"إجمالي الطلب: {self.current_order['total']} جنيه")
        
        # Add delivery info if available
        if self.current_order["address"]:
            summary_parts.append(f"العنوان: {self.current_order['address']}")
            
        if self.current_order["phone"]:
            summary_parts.append(f"رقم الهاتف: {self.current_order['phone']}")
            
        if self.current_order.get("special_instructions"):
            summary_parts.append(f"تعليمات خاصة: {self.current_order['special_instructions']}")
            
        # Add estimated delivery time
        estimated_time = self.get_estimated_delivery_time()
        summary_parts.append(f"وقت التوصيل المتوقع: {estimated_time} دقيقة")
        
        return "\n".join(summary_parts)

    def finalize_order(self) -> OrderConfirmationResult:
        """Finalize the current order and return a confirmation."""
        if not self.current_order:
            raise ValueError("No active order")

        if not self.current_order["items"]:
            raise ValueError("Order has no items")

        if not self.current_order["address"] or not self.current_order["phone"]:
            raise ValueError("Missing delivery information")

        # In a real system, we would save the order to a database here
        order_id = self.next_order_id
        self.next_order_id += 1

        estimated_time = self.get_estimated_delivery_time()
        order_summary = self.get_order_summary()

        return OrderConfirmationResult(
            order=self.current_order, 
            estimated_time=estimated_time,
            order_summary=order_summary
        )

    def clear_order(self) -> None:
        """Clear the current order."""
        self.current_order = None


# Create order manager instance
order_manager = OrderManager()


# Function handlers for the LLM
async def get_menu() -> Union[MenuResult, ErrorResult]:
    """Handler for fetching the shawarma menu."""
    logger.debug("Fetching shawarma menu")
    try:
        return MenuResult(menu=SHAWARMA_MENU)
    except Exception as e:
        logger.error(f"Error fetching menu: {e}")
        return ErrorResult(status="error", error="فشل في عرض القائمة")


async def get_extras() -> Union[ExtrasResult, ErrorResult]:
    """Handler for fetching available extras."""
    logger.debug("Fetching extras options")
    try:
        return ExtrasResult(extras=EXTRAS)
    except Exception as e:
        logger.error(f"Error fetching extras: {e}")
        return ErrorResult(status="error", error="فشل في عرض الإضافات")


async def select_shawarma_order(args: FlowArgs) -> OrderResult:
    """Handle shawarma type, quantity and extras selection."""
    try:
        item_type = args["item_type"]
        quantity = args["quantity"]
        extras = args.get("extras", [])

        logger.debug(f"Adding to order: {item_type} x{quantity} with extras: {extras}")

        new_item = order_manager.add_item(item_type, quantity, extras)
        price = order_manager.calculate_item_price(new_item)
        
        return OrderResult(item=new_item, price=price)
    except Exception as e:
        logger.error(f"Error adding to order: {e}")
        return ErrorResult(status="error", error="فشل في إضافة الطلب")


async def set_delivery_info(args: FlowArgs) -> OrderDetailsResult:
    """Handle setting delivery information."""
    try:
        address = args["address"]
        phone = args["phone"]
        special_instructions = args.get("special_instructions", None)

        logger.debug(f"Setting delivery details: Address={address}, Phone={phone}")
        
        # Set delivery info
        order_manager.set_delivery_info(address, phone, special_instructions)
        estimated_time = order_manager.get_estimated_delivery_time()
        
        return OrderDetailsResult(
            address=address,
            phone=phone,
            special_instructions=special_instructions,
            estimated_time=estimated_time
        )
    except Exception as e:
        logger.error(f"Error setting delivery details: {e}")
        return ErrorResult(status="error", error="فشل في تأكيد معلومات التوصيل")


async def check_kitchen_status(action: dict) -> None:
    """Check if kitchen is open and ready to take orders."""
    logger.info("checking kitchen status - مطبخ شاورما بلدنا جاهز للطلبات")


async def end_conversation_handler(action: dict) -> None:
    """Handle the end_conversation action by scheduling call termination."""
    logger.info("End conversation action triggered")
    
    # Schedule call termination after a delay to allow for final message
    asyncio.create_task(end_call_after_delay(5))


async def end_call_after_delay(delay_seconds: int = 3):
    """End the call after a specified delay."""
    logger.info(f"Call will end in {delay_seconds} seconds")
    await asyncio.sleep(delay_seconds)
    logger.info("Ending call now")
    
    # Queue an EndFrame to terminate the call
    if task := globals().get("_pipeline_task"):
        await task.queue_frame(EndFrame())
        logger.info("EndFrame queued successfully")
    else:
        logger.error("Could not access pipeline task to end call")


async def complete_order() -> FlowResult:
    """Handler for completing the order and ending the conversation."""
    logger.debug("Order completed successfully")
    # In a real system, we would submit the order to a backend system here
    
    # Return a result to transition to the end node, which will handle call termination
    return FlowResult()


async def revise_order() -> FlowResult:
    """Handler for revising the current order."""
    logger.debug("Revising order - returning to order items stage")
    # We don't need to clear the order, just return to the order items stage
    return FlowResult()


async def tts_say_handler(action: dict) -> None:
    """Handle TTS say action for post_actions."""
    text = action.get("text", "")
    if text:
        logger.info(f"TTS saying: {text}")
        # The actual TTS handling is done by the pipeline


# Flow configuration
flow_config: FlowConfig = {
    "initial_node": "start",
    "nodes": {
        "start": {
            "role_messages": [
                {
                    "role": "system",
                    "content": """
# Shawarma Ordering Bot - Flow Structure and Function Guide

You are an Egyptian shawarma restaurant order-taker on a phone call, speaking casual Egyptian Arabic dialect.

## Flow Structure
1. START NODE (current): Initial greeting and menu inquiries
2. ORDER_ITEMS NODE: Collecting shawarma type, quantity, extras
3. DELIVERY_INFO NODE: Collecting delivery address and phone number
4. CONFIRM NODE: Order summary and confirmation
5. END NODE: Thank customer and end conversation

## Functions to Use
- get_menu(): ONLY when customer explicitly asks for menu options
- start_ordering(): When customer wants to place an order without seeing menu
- select_shawarma_order(): When customer specifies type, quantity, and extras
- set_delivery_info(): When customer provides complete address and phone number
- complete_order(): When customer confirms the final order
- revise_order(): When customer wants to modify their order

## In this START node:
- Begin with a casual Egyptian greeting
- Answer menu questions with get_menu()
- Transition to order_items with start_ordering() when customer is ready to order

أنت موظف استقبال طلبات في مطعم شاورما مصري. تتحدث باللهجة المصرية العامية الدارجة ولديك شخصية ودية وخفيفة الظل.
اجعل ردودك قصيرة وعفوية مثل المكالمة الهاتفية الحقيقية. 




لا تعرض القائمة تلقائياً. انتظر حتى يسأل العميل عنها. لا تستبق طلبات العميل أو تفترض ما يريده.
لا تستخدم لغة رسمية أبداً. استخدم مصطلحات مصرية شائعة مثل "يا باشا"، "يا فندم"، "إزيك"، "حاضر"، "زي الفل".
                    """,
                }
            ],
            "task_messages": [
                {
                    "role": "system",
                    "content": """
ابدأ المكالمة بشكل طبيعي وقصير، مثل: "ألو، شاورما بلدنا"، أو "أيوة، شاورما بلدنا معاك".
انتظر رد العميل. إذا سأل عن القائمة تحديداً، استخدم get_menu. لكن في معظم الحالات سيبدأ العميل بالطلب مباشرة.
                    """,
                }
            ],
            "pre_actions": [
                {
                    "type": "check_kitchen",
                    "handler": check_kitchen_status,
                },
            ],
            "functions": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_menu",
                        "handler": get_menu,
                        "description": "عرض قائمة السندوتشات المتاحة مع الأسعار، يستخدم فقط إذا سأل العميل عن القائمة",
                        "parameters": {"type": "object", "properties": {}},
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "start_ordering",
                        "description": "الانتقال إلى مرحلة الطلب بدون عرض القائمة كاملة",
                        "parameters": {"type": "object", "properties": {}},
                        "transition_to": "order_items",
                    },
                },
            ],
        },
        "order_items": {
            "task_messages": [
                {
                    "role": "system",
                    "content": """
# ORDER_ITEMS Node Instructions

## Purpose
In this node, you collect the customer's shawarma order details.

## Function Usage
- select_shawarma_order(): Call this when the customer has clearly specified:
  1. Shawarma type (chicken/meat/mix)
  2. Quantity (how many sandwiches)
  3. Any extras they want (optional)
- get_menu(): Call this if customer needs to see the menu again

## Transition Logic
- Only transition to delivery_info after getting complete order details
- Make sure to confirm the order items before proceeding

## Menu Prices
- Chicken shawarma: 65 EGP
- Meat shawarma: 85 EGP
- Mix shawarma: 75 EGP
- Extras: Fries (25 EGP), Cheese (10 EGP), Garlic sauce (5 EGP), Extra tahini (5 EGP)

أنت تتعامل مع طلب شاورما. استخدم الوظائف المتاحة:
- استخدم select_shawarma_order عندما يحدد العميل النوع والكمية والإضافات المطلوبة
- لا تستعجل العميل وتأكد من فهم طلبه بشكل صحيح قبل تسجيله

الأسعار:
- شاورما فراخ: 65 جنيه
- شاورما لحمة: 85 جنيه
- شاورما مكس: 75 جنيه
- إضافات: بطاطس (25 جنيه)، جبنة (10 جنيه)، صوص ثوم (5 جنيه)، طحينة إضافية (5 جنيه)
                    """,
                }
            ],
            "functions": [
                {
                    "type": "function",
                    "function": {
                        "name": "select_shawarma_order",
                        "handler": select_shawarma_order,
                        "description": "تسجيل تفاصيل طلب الشاورما",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "item_type": {
                                    "type": "string",
                                    "enum": ["chicken", "meat", "mix"],
                                    "description": "نوع الشاورما",
                                },
                                "quantity": {
                                    "type": "integer",
                                    "description": "عدد السندوتشات",
                                },
                                "extras": {
                                    "type": "array",
                                    "items": {
                                        "type": "string",
                                        "enum": [
                                            "fries",
                                            "cheese",
                                            "garlic_sauce",
                                            "tahini_extra",
                                        ],
                                    },
                                    "description": "الإضافات المطلوبة",
                                },
                            },
                            "required": ["item_type", "quantity"],
                        },
                        "transition_to": "delivery_info",
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_menu",
                        "handler": get_menu,
                        "description": "عرض قائمة الشاورما المتاحة",
                        "parameters": {"type": "object", "properties": {}},
                    },
                },
            ],
        },
        "delivery_info": {
            "task_messages": [
                {
                    "role": "system",
                    "content": """
# DELIVERY_INFO Node Instructions

## Purpose
In this node, you collect complete delivery information from the customer.

## Function Usage
- set_delivery_info(): Call this ONLY when you have collected:
  1. Complete delivery address (street, building number, apartment)
  2. Valid phone number
  3. Any special delivery instructions (optional)

## Important Guidelines
- Get detailed address information - vague addresses are not acceptable
- Ensure the phone number is valid (at least 8-11 digits)
- Repeat back the address and phone number to confirm accuracy
- Only transition to confirm node when all required information is collected

## Transition Logic
This node transitions to the confirm node when set_delivery_info() is called with valid data.

اطلب معلومات التوصيل من العميل:
- اطلب العنوان بالتفصيل (المنطقة، الشارع، رقم المبنى، الشقة)
- اطلب رقم الهاتف
- اسأل عن أي تعليمات خاصة للتوصيل

استخدم الوظائف المتاحة:
- استخدم set_delivery_info عندما يقدم العميل عنوان وصول صحيح ورقم هاتف
                    """,
                }
            ],
            "functions": [
                {
                    "type": "function",
                    "function": {
                        "name": "set_delivery_info",
                        "handler": set_delivery_info,
                        "description": "تسجيل معلومات التوصيل",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "address": {
                                    "type": "string",
                                    "description": "عنوان التوصيل بالتفصيل",
                                },
                                "phone": {
                                    "type": "string",
                                    "description": "رقم الهاتف للتواصل",
                                },
                                "special_instructions": {
                                    "type": "string",
                                    "description": "تعليمات خاصة للتوصيل (اختياري)",
                                },
                            },
                            "required": ["address", "phone"],
                        },
                        "transition_to": "confirm",
                    },
                },
            ],
        },
        "confirm": {
            "task_messages": [
                {
                    "role": "system",
                    "content": """
# CONFIRM Node Instructions

## Purpose
In this node, you summarize the complete order and get final confirmation from the customer.

## Function Usage
- complete_order(): Call this when customer explicitly confirms the order is correct
- revise_order(): Call this when customer wants to change any part of their order

## Required Actions
1. Summarize the complete order in detail:
   - All shawarma items, quantities and extras
   - Total price
   - Delivery address and phone number
   - Estimated delivery time

2. Ask explicitly if the customer wants to:
   - Confirm the order as is (use complete_order)
   - Make changes to the order (use revise_order)

## Transition Logic
- complete_order transitions to the end node
- revise_order transitions back to the start node

لخص تفاصيل الطلب كاملة للعميل واسأله إذا كان يريد تأكيد الطلب أو إجراء تغييرات. استخدم الوظائف المتاحة:
- استخدم complete_order عندما يؤكد العميل أن الطلب صحيح ولا يريد إجراء تغييرات
- استخدم revise_order إذا أراد تغيير شيء ما

اقرأ تفاصيل الطلب بوضوح، بما في ذلك:
- نوع وكمية الشاورما والإضافات
- العنوان ورقم الهاتف
- وقت التوصيل المتوقع
- إجمالي السعر
                    """,
                }
            ],
            "functions": [
                {
                    "type": "function",
                    "function": {
                        "name": "complete_order",
                        "description": "العميل يؤكد أن الطلب صحيح",
                        "parameters": {"type": "object", "properties": {}},
                        "transition_to": "end",
                        "handler": complete_order,
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "revise_order",
                        "description": "العميل يريد إجراء تغييرات على الطلب",
                        "parameters": {"type": "object", "properties": {}},
                        "transition_to": "start",
                        "handler": revise_order,
                    },
                },
            ],
        },
        "end": {
            "task_messages": [
                {
                    "role": "system",
                    "content": """
# END Node Instructions

## Purpose
In this final node, you thank the customer and gracefully end the conversation.

## Key Points
1. Express gratitude for the order
2. Confirm that their order has been successfully recorded
3. Remind them of the estimated delivery time
4. Say goodbye in a friendly, Egyptian way

## Post Actions
After your final message, the system will:
1. Play a TTS goodbye message
2. End the conversation

No function calls are available in this node. The conversation will end automatically.

اشكر العميل على طلبه وأنهِ المحادثة بشكل مهذب ومختصر. أخبر العميل بوضوح:
- أن طلبه تم تسجيله بنجاح
- أنه سيصل خلال الوقت المتوقع
- أنك ستنهي المكالمة الآن
                    """,
                }
            ],
            "functions": [],
            "post_actions": [
                {"type": "tts_say", "text": "شكراً لطلبك، مع السلامة"},
                {"type": "end_conversation", "handler": end_conversation_handler}
            ],
        },
    },
}


# Register custom action handlers
async def register_custom_actions(flow_manager: FlowManager) -> None:
    """Register custom actions for the flow manager."""
    logger.info("Registering custom action handlers")
    
    # Register TTS action handler
    flow_manager.register_action("tts_say", tts_say_handler)
    
    # Register end conversation action handler
    flow_manager.register_action("end_conversation", end_conversation_handler)
    
    # Register kitchen status check action handler
    flow_manager.register_action("check_kitchen", check_kitchen_status)

    logger.info("Action handlers registered successfully")


async def main():
    """Main function to set up and run the shawarma ordering bot."""
    # Get the room URL from environment variables
    daily_room_url = os.getenv("DAILY_ROOM_URL")
    if not daily_room_url:
        logger.error("DAILY_ROOM_URL environment variable is not set")
        sys.exit(1)

    logger.info(f"Using room URL: {daily_room_url}")

    # Configure the Daily transport
    transport = DailyTransport(
        daily_room_url,
        os.getenv("DAILY_ROOM_TOKEN"),
        "شاورما بلدنا",
        DailyParams(
            audio_out_enabled=True,
            audio_out_sample_rate=24000,
            transcription_enabled=False,
            vad_enabled=True,
            vad_analyzer=SileroVADAnalyzer(
                sample_rate=16000,
                params=VADParams(
                    threshold=0.5,
                    min_speech_duration_ms=250,
                    min_silence_duration_ms=100
                )
            ),
            vad_audio_passthrough=True,
        ),
    )

    # Configure with voice customization
    tts = ElevenLabsTTSService(
        api_key=os.getenv("ELEVENLABS_API_KEY"),
        voice_id="IES4nrmZdUBHByLBde0P",
        model="eleven_multilingual_v2",
        params=ElevenLabsTTSService.InputParams(
            stability=0.7, similarity_boost=0.8, style=0.5, use_speaker_boost=True
        ),
    )

    # Configure service
    stt = AzureSTTService(
        api_key=os.getenv("AZURE_STT_API_KEY"),
        region="uaenorth",
        language="ar-EG",
        sample_rate=24000,
        channels=1,
    )

    llm = OpenAILLMService(
        api_key=os.getenv("OPENAI_API_KEY"), model="gpt-4o", temperature=0.3
    )

    context = OpenAILLMContext()
    context_aggregator = llm.create_context_aggregator(context)
    # Initialize RTVI processors
    rtvi_speaking = RTVISpeakingProcessor()
    rtvi_user_transcription = RTVIUserTranscriptionProcessor()
    rtvi_bot_transcription = RTVIBotTranscriptionProcessor()
    rtvi_bot_llm = RTVIBotLLMProcessor()
    rtvi_bot_tts = RTVIBotTTSProcessor(direction=FrameDirection.DOWNSTREAM)
    rtvi_metrics = RTVIMetricsProcessor()

    # Initialize transcript processor for context
    transcript = TranscriptProcessor()

    pipeline = Pipeline(
        [
            transport.input(),  # Transport input
            rtvi_speaking,  # Speaking state
            stt,  # STT
            rtvi_user_transcription,  # Process user transcripts for RTVI
            transcript.user(),  # Process user messages for context
            context_aggregator.user(),  # User responses
            llm,  # LLM
            rtvi_bot_llm,  # Process LLM responses for RTVI
            tts,  # TTS
            rtvi_bot_tts,  # Process TTS for RTVI
            rtvi_bot_transcription,  # Process bot transcripts for RTVI
            transport.output(),  # Transport output
            transcript.assistant(),  # Process assistant messages for context
            context_aggregator.assistant(),  # Assistant responses
            rtvi_metrics,  # Collect metrics
        ]
    )

    task = PipelineTask(pipeline, PipelineParams(allow_interruptions=True))
    
    # Store the pipeline task in a global variable for access by end_call_after_delay
    global _pipeline_task
    _pipeline_task = task
    
    # Initialize flow manager with RTVI context
    flow_manager = FlowManager(
        task=task,
        llm=llm,
        context_aggregator=context_aggregator,
        tts=tts,
        flow_config=flow_config,
    )
    
    # Register custom action handlers
    await register_custom_actions(flow_manager)

    @transport.event_handler("on_first_participant_joined")
    async def on_first_participant_joined(transport, participant):
        await transport.capture_participant_transcription(participant["id"])
        logger.info("Initializing flow manager and starting conversation")
        
        # Initialize the flow
        await flow_manager.initialize()

        # Schedule immediate check for order existence
        asyncio.create_task(check_order_exists())

    # Create a separate function to check and handle order existence
    async def check_order_exists():
        """Check that an order exists and create one if not."""
        logger.info("Checking if order exists")
        if not order_manager.current_order:
            logger.warning("No order found, creating a new one")
            order_manager.create_new_order()
            
    runner = PipelineRunner()
    
    await runner.run(task)


if __name__ == "__main__":
    asyncio.run(main())
