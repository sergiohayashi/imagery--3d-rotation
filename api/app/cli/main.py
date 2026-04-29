import argparse
import asyncio
import time
from app.cli.commands import (
    chat_runner_2_1,
    chat_runner_2_2,
    chat_runner_2_3_chatgpt5_5,
    chat_runner_2_4_chatgpt5_2,
    chat_runner_2_5_chatgpt5_4,
    eval_runner_05095,
    eval_runner_05097,
    eval_runner_08101_prompt1,
    eval_runner_08101_prompt1_v2,
    eval_runner_08101_prompt2,
    eval_runner_08101_prompt3,
    eval_runner_08101_prompt3_freeze1,
    eval_runner_08101_prompt3_freeze1_abla1,
    eval_runner_08101_prompt3_freeze2,
    eval_runner_08101_prompt4,
    eval_runner_08101_prompt4_v2,
    eval_runner_08101_prompt5,
    eval_runner_08101_prompt6,
    eval_runner_08101_prompt6_v2,
    eval_runner_08103_p1,
    eval_runner_08103_p2,
    eval_runner_08103_p3,
    eval_runner_08104_p1,
    eval_runner_08104_p10,
    eval_runner_08104_p9,
    eval_runner_08201_prompt3_freeze1,
    eval_runner_09101_prompt3_freeze1,
    eval_runner_4,
    eval_runner_5,
    eval_runner_6,
    eval_runner_7,
    eval_runner_8,
    eval_runner_9,
    eval_runner_90,
    eval_runner_91,
    eval_runner_92,
    eval_runner_07099_prompt1,
    eval_runner_07099_prompt2,
    eval_runner_07099_prompt3,
    eval_runner_93,
    eval_runner_94,
    eval_runner_95,
    eval_runner_with_model_9,
    hello_example,
    chat_runner_1,
    eval_runner_96,
    eval_runner_05009,
    eval_runner_05094,
    eval_runner_05096,
    eval_runner_05097_1,
    eval_runner_05097_2,
    eval_runner_05097_3,
    eval_runner_05098,
    eval_runner_07099,
    eval_runner_08101,
    eval_runner_08102,
    eval_runner_9_1
)

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="OpBoost CLI — async-enabled command line interface."
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Register all commands
    hello_example.register(subparsers)
    chat_runner_1.register(subparsers)
    chat_runner_2_1.register(subparsers)
    chat_runner_2_2.register(subparsers)
    chat_runner_2_3_chatgpt5_5.register(subparsers)
    chat_runner_2_4_chatgpt5_2.register(subparsers)
    chat_runner_2_5_chatgpt5_4.register(subparsers)
    eval_runner_4.register(subparsers)
    eval_runner_5.register(subparsers)
    eval_runner_6.register(subparsers)
    eval_runner_7.register(subparsers)
    eval_runner_8.register(subparsers)
    eval_runner_9.register(subparsers)
    eval_runner_9_1.register(subparsers)
    eval_runner_90.register(subparsers)
    eval_runner_91.register(subparsers)
    eval_runner_92.register(subparsers)
    eval_runner_with_model_9.register(subparsers)
    eval_runner_93.register(subparsers)
    eval_runner_94.register(subparsers)
    eval_runner_95.register(subparsers)
    eval_runner_96.register(subparsers)
    eval_runner_05009.register(subparsers)
    eval_runner_05094.register(subparsers)
    eval_runner_05095.register(subparsers)
    eval_runner_05096.register(subparsers)
    eval_runner_05097.register(subparsers)
    eval_runner_05097_1.register(subparsers)
    eval_runner_05097_2.register(subparsers)
    eval_runner_05097_3.register(subparsers)
    eval_runner_05098.register(subparsers)
    eval_runner_07099.register(subparsers)
    eval_runner_08101.register(subparsers)
    eval_runner_08102.register(subparsers)
    eval_runner_07099_prompt1.register(subparsers)
    eval_runner_07099_prompt2.register(subparsers)
    eval_runner_07099_prompt3.register(subparsers)
    eval_runner_08101_prompt1.register(subparsers)
    eval_runner_08101_prompt1_v2.register(subparsers)
    eval_runner_08101_prompt3.register(subparsers)
    eval_runner_08101_prompt2.register(subparsers)
    eval_runner_08101_prompt4.register(subparsers)
    eval_runner_08101_prompt4_v2.register(subparsers)
    eval_runner_08101_prompt6_v2.register(subparsers)
    eval_runner_08101_prompt5.register(subparsers)
    eval_runner_08101_prompt6.register(subparsers)
    eval_runner_08103_p1.register(subparsers)
    eval_runner_08103_p2.register(subparsers)
    eval_runner_08104_p1.register(subparsers)
    eval_runner_08103_p3.register(subparsers)
    eval_runner_08104_p9.register(subparsers)
    eval_runner_08104_p10.register(subparsers)
    eval_runner_08101_prompt3_freeze1.register(subparsers)
    eval_runner_09101_prompt3_freeze1.register(subparsers)
    eval_runner_08201_prompt3_freeze1.register(subparsers)
    eval_runner_08101_prompt3_freeze2.register(subparsers)
    eval_runner_08101_prompt3_freeze1_abla1.register(subparsers)
    return parser


def main():
    # Use perf_counter instead of time()
    start_time = time.perf_counter()

    parser = build_parser()  # Assuming build_parser is defined elsewhere
    args = parser.parse_args()

    # Run the handler (sync or async)
    handler_cls = args.handler
    handler = handler_cls(args)

    if handler is None:
        parser.print_help()
        return

    asyncio.run(handler())

    # Use perf_counter instead of time()
    end_time = time.perf_counter()

    # Optional: Format to a specific number of decimal places (e.g., .4f)
    print(f"Elapsed time: {end_time - start_time:.4f} seconds")


if __name__ == "__main__":
    main()

