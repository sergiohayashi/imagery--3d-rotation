def register(subparsers):
    parser = subparsers.add_parser("hello", help="Say Hello")
    parser.add_argument("--greeting", required=False)
    parser.set_defaults(handler=HelloCommandExample)


class HelloCommandExample:
    def __init__(self, args):
        self.args = args

    async def __call__(self):
        print("Hello!", self.args)
