import argparse
import os

import dotenv

dotenv.load_dotenv()

from remind.webui.ui import get_ui


def launch(args):
    demo = get_ui()
    demo.queue(default_concurrency_limit=None)
    demo.launch(
        server_name="0.0.0.0",
        show_error=True,
        share=args.share,
        auth=(os.environ.get("GRADIO_USERNAME", "admin"), os.environ.get("GRADIO_PASSWORD", "admin")) if args.share else None,
        favicon_path="assets/brain.png",
    )

if __name__ == "__main__":
    argparser = argparse.ArgumentParser()
    argparser.add_argument("--share", action="store_true", help="Get public link")
    args = argparser.parse_args()
    launch(args)
