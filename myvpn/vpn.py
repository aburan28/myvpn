from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
import logging

def main():
    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    subparsers = parser.add_subparsers(title="commands")
    subcommands = [
        ('server', 'server', "Run in server mode"),
        ('client', 'client', "Run in client mode"),
        ('ssh', 'ssh', "Run in ssh tunnel"),
    ]
    for command, module_name, help_text in subcommands:
        subparser = subparsers.add_parser(command, help=help_text)
        subparser.add_argument('-v', '--verbose', action='store_true',
                               help="enable additional output")
        module = __import__(module_name, globals(), locals(),
                            ['populate_argument_parser', 'main'], 1)
        module.populate_argument_parser(subparser)
        subparser.set_defaults(func=module.main)

    args = parser.parse_args()
    loglevel = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=loglevel)

    return args.func(args)
