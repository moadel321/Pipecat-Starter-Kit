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
from pipecat_flows import FlowArgs, FlowConfig, FlowManager, FlowResult
from pipecat.transcriptions.language import Language


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


class Order(TypedDict):
    items: List[OrderItem]
    address: str
    phone: str
    total: int


class MenuResult(FlowResult):
    menu: Dict[str, MenuItem]


class ExtrasResult(FlowResult):
    extras: Dict[str, ExtraItem]


class OrderItemResult(FlowResult):
    item: OrderItem


class OrderConfirmationResult(FlowResult):
    order: Order
    estimated_time: int  # in minutes


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
        self.current_order = {"items": [], "address": "", "phone": "", "total": 0}
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

    def set_delivery_info(self, address: str, phone: str) -> Order:
        """Set delivery information for the current order."""
        if not self.current_order:
            raise ValueError("No active order")

        self.current_order["address"] = address
        self.current_order["phone"] = phone

        return self.current_order

    def get_estimated_delivery_time(self) -> int:
        """Calculate estimated delivery time in minutes."""
        # Simple estimation: 15 minutes base + 5 minutes per item
        if not self.current_order or not self.current_order["items"]:
            return 30  # Default time

        return 15 + (5 * sum(item["quantity"] for item in self.current_order["items"]))

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

        return OrderConfirmationResult(
            order=self.current_order, estimated_time=estimated_time
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


async def add_to_order(args: FlowArgs) -> Union[OrderItemResult, ErrorResult]:
    """Handler for adding items to the order."""
    try:
        item_type = args["item_type"]
        quantity = args["quantity"]
        extras = args.get("extras", [])

        logger.debug(f"Adding to order: {item_type} x{quantity} with extras: {extras}")

        new_item = order_manager.add_item(item_type, quantity, extras)
        return OrderItemResult(item=new_item)
    except Exception as e:
        logger.error(f"Error adding to order: {e}")
        return ErrorResult(status="error", error="فشل في إضافة الطلب")


async def set_delivery_details(
    args: FlowArgs,
) -> Union[OrderConfirmationResult, ErrorResult]:
    """Handler for setting delivery details and finalizing the order."""
    try:
        address = args["address"]
        phone = args["phone"]

        logger.debug(f"Setting delivery details: Address={address}, Phone={phone}")

        order_manager.set_delivery_info(address, phone)
        confirmation = order_manager.finalize_order()
        return confirmation
    except Exception as e:
        logger.error(f"Error setting delivery details: {e}")
        return ErrorResult(status="error", error="فشل في تأكيد معلومات التوصيل")


async def cancel_order() -> FlowResult:
    """Handler for canceling the current order."""
    logger.debug("Canceling order")
    order_manager.clear_order()
    return FlowResult()


# Flow configuration
flow_config: FlowConfig = {
    "initial_node": "greeting",
    "nodes": {
        "greeting": {
            "role_messages": [
                {
                    "role": "system",
                    "content": """
أنت موظف استقبال طلبات في مطعم شاورما مصري. تتحدث باللهجة المصرية العامية الدارجة ولديك شخصية ودية وخفيفة الظل.
اجعل ردودك قصيرة وعفوية مثل المكالمة الهاتفية الحقيقية. 

هكذا يتحدث الناس على الهاتف في مصر:
- "ألو، شاورما بلدنا"
- "أيوة يا فندم، عايز تطلب إيه؟"
- "أيوة معايا"
- "تمام يا باشا"
- "حضرتك عايز فراخ ولا لحمة؟"
- "طبعا ممكن حضرتك"
- "هيوصل خلال نص ساعة بالظبط"

لا تعرض القائمة تلقائياً. انتظر حتى يسأل العميل عنها. لا تستبق طلبات العميل أو تفترض ما يريده.
لا تستخدم لغة رسمية أبداً. استخدم مصطلحات مصرية شائعة مثل "يا باشا"، "يا فندم"، "إزيك"، "حاضر"، "زي الفل".

تذكر دائمًا:
1. استخدم جمل قصيرة جداً كما في المحادثات الهاتفية الحقيقية
2. اسأل فقط سؤال واحد في كل مرة
3. لا تقدم الكثير من المعلومات دفعة واحدة
4. اجعل الردود عفوية وطبيعية كأنها محادثة حقيقية
                    """,
                }
            ],
            "task_messages": [
                {
                    "role": "system",
                    "content": """
ابدأ المكالمة بشكل طبيعي وقصير، مثل: "ألو، شاورما بلدنا"، أو "أيوة، شاورما بلدنا معاك".
انتظر رد العميل. إذا سأل عن القائمة تحديداً، استخدم get_menu. لكن في معظم الحالات سيبدأ العميل بالطلب مباشرة مثل "عايز شاورما فراخ" أو "عندكم شاورما لحمة؟"
استجب بشكل طبيعي لما يقوله العميل، مثلاً: "أيوة طبعاً عندنا، حضرتك عايز كام واحد؟"
                    """,
                }
            ],
            "functions": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_menu",
                        "handler": get_menu,
                        "description": "عرض قائمة السندوتشات المتاحة مع الأسعار، يستخدم فقط إذا سأل العميل عن القائمة",
                        "parameters": {"type": "object", "properties": {}},
                        "transition_to": "order_items",
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
تعامل مع طلبات العميل بشكل طبيعي ومتدفق:

- إذا طلب العميل شاورما معينة، استخدم add_to_order واسأله عن الكمية أو الإضافات بشكل طبيعي
  مثلاً: "شاورما فراخ، تمام. عايزها واحدة ولا اتنين؟" أو "حضرتك عايز معاها بطاطس؟"

- إذا سأل العميل عن الإضافات المتاحة فقط، استخدم get_extras

- بعد إضافة كل صنف، اسأل بشكل طبيعي: "حضرتك عايز حاجة تانية؟" أو "فيه أي إضافات تانية؟"

- عندما يشير العميل إلى أنه انتهى (مثلاً يقول "خلاص كده" أو "بس كده")، اسأله: "أؤكد الطلب؟ أو عايز حاجة تانية؟"

- استخدم complete_ordering عندما ينتهي العميل من الطلب وتحتاج للانتقال لمعلومات التوصيل

- كن مرناً وطبيعياً في الحوار، واستمع لما يقوله العميل بدلاً من اتباع سيناريو ثابت
                    """,
                }
            ],
            "functions": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_extras",
                        "handler": get_extras,
                        "description": "عرض الإضافات المتاحة مع الأسعار، فقط إذا طلب العميل معرفة الإضافات",
                        "parameters": {"type": "object", "properties": {}},
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "add_to_order",
                        "handler": add_to_order,
                        "description": "إضافة سندوتش إلى الطلب",
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
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "cancel_order",
                        "handler": cancel_order,
                        "description": "إلغاء الطلب الحالي",
                        "parameters": {"type": "object", "properties": {}},
                        "transition_to": "end",
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "complete_ordering",
                        "description": "إنهاء الطلب والانتقال لمعلومات التوصيل",
                        "parameters": {"type": "object", "properties": {}},
                        "transition_to": "delivery_info",
                    },
                },
            ],
        },
        "delivery_info": {
            "task_messages": [
                {
                    "role": "system",
                    "content": """
اسأل عن معلومات التوصيل بشكل طبيعي وبسيط:

"طيب ممكن العنوان؟"
انتظر حتى يعطي العميل العنوان

ثم اسأل: "ورقم التليفون لو سمحت؟"
انتظر حتى يعطي العميل رقم الهاتف

استخدم set_delivery_details فقط بعد الحصول على المعلومات كاملة. قبل تأكيد الطلب، كرر العنوان بشكل سريع للتأكد من صحته.
مثلاً: "يعني هوصل على [العنوان]، صح كده؟"
                    """,
                }
            ],
            "functions": [
                {
                    "type": "function",
                    "function": {
                        "name": "set_delivery_details",
                        "handler": set_delivery_details,
                        "description": "ضبط معلومات التوصيل وتأكيد الطلب",
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
                            },
                            "required": ["address", "phone"],
                        },
                        "transition_to": "confirmation",
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "cancel_order",
                        "handler": cancel_order,
                        "description": "إلغاء الطلب الحالي",
                        "parameters": {"type": "object", "properties": {}},
                        "transition_to": "end",
                    },
                },
            ],
        },
        "confirmation": {
            "task_messages": [
                {
                    "role": "system",
                    "content": """
أكد الطلب بشكل سريع ومختصر، مثل شخص مشغول يتحدث على الهاتف:

"تمام يا فندم، الطلب هيكون [اذكر الأصناف بسرعة] بإجمالي [السعر] جنيه، وهيوصل خلال [الوقت المتوقع] دقيقة.
شكراً لحضرتك، الدليفري هيتصل بحضرتك لما يوصل."

اجعل التأكيد سريعاً وعملياً كما يحدث في المكالمات الهاتفية الحقيقية، دون تفاصيل زائدة.
                    """,
                }
            ],
            "functions": [],
            "post_actions": [{"type": "end_conversation"}],
        },
        "end": {
            "task_messages": [
                {
                    "role": "system",
                    "content": "أنه المكالمة بشكل طبيعي وقصير. إذا ألغى العميل الطلب، قل شيئاً مثل 'تمام يا فندم، في أي وقت تاني اتصل بينا'. إذا كان هناك خطأ أو مشكلة، اعتذر بإيجاز.",
                }
            ],
            "functions": [],
            "post_actions": [{"type": "end_conversation"}],
        },
    },
}


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
            vad_analyzer=SileroVADAnalyzer(),
            vad_audio_passthrough=True
        ),
    )

    # Configure with voice customization
    tts = ElevenLabsTTSService(
        api_key=os.getenv("ELEVENLABS_API_KEY"),
        voice_id="IES4nrmZdUBHByLBde0P",
        model="eleven_multilingual_v2",
        params=ElevenLabsTTSService.InputParams(
            stability=0.7,
        similarity_boost=0.8,
        style=0.5,
        use_speaker_boost=True
    )
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
        api_key=os.getenv("OPENAI_API_KEY"), model="gpt-4o-mini", temperature=0.3
    )

    context = OpenAILLMContext()
    context_aggregator = llm.create_context_aggregator(context)

    transcript = TranscriptProcessor()

    pipeline = Pipeline(
        [
            transport.input(),  # Transport input
            stt,  # STT
            transcript.user(),  # Process user messages for context
            context_aggregator.user(),  # User responses
            llm,  # LLM
            tts,  # TTS
            transport.output(),  # Transport output
            transcript.assistant(),  # Process assistant messages for context
            context_aggregator.assistant(),  # Assistant responses
        ]
    )

    task = PipelineTask(pipeline, PipelineParams(allow_interruptions=True))

    # Initialize flow manager with RTVI context
    flow_manager = FlowManager(
        task=task,
        llm=llm,
        context_aggregator=context_aggregator,
        flow_config=flow_config,
    )

    @transport.event_handler("on_first_participant_joined")
    async def on_first_participant_joined(transport, participant):
        await transport.capture_participant_transcription(participant["id"])
        await flow_manager.initialize()

    runner = PipelineRunner()
    await runner.run(task)


if __name__ == "__main__":
    asyncio.run(main())
