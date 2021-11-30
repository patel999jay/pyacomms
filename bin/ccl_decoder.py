import argparse
from acomms import ccl


def do_decode(hex_data):
    ccl_msg = ccl.CclDecoder.decode_hex_string(hex_data)
    for (name, value) in list(ccl_msg.items()):
        human_readable = '{}\t{}'.format(name, value).expandtabs(24)
        print(human_readable)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Decode a CCL message into human-readable things.')
    ap.add_argument("hex_data", help="Hex encoded data (RXD payload)")

    args = ap.parse_args()

    do_decode(args.hex_data)

