# File: pyCraft/start.py

from __future__ import print_function

import getpass
import sys
import re
import json
from optparse import OptionParser

from color import Colors

import sys
sys.path.append("../pyCraft")

from minecraft import authentication
from minecraft.exceptions import YggdrasilError
from minecraft.networking.connection import Connection
from minecraft.networking.packets import Packet, clientbound, serverbound
from minecraft.compat import input


def get_options():
    parser = OptionParser()

    parser.add_option("-u", "--username", dest="username", default=None,
                      help="username to log in with")

    parser.add_option("-p", "--password", dest="password", default=None,
                      help="password to log in with")

    parser.add_option("-s", "--server", dest="server", default=None,
                      help="server host or host:port "
                           "(enclose IPv6 addresses in square brackets)")

    parser.add_option("-o", "--offline", dest="offline", action="store_true",
                      help="connect to a server in offline mode "
                           "(no password required)")

    parser.add_option("-d", "--dump-packets", dest="dump_packets",
                      action="store_true",
                      help="print sent and received packets to standard error")

    (options, args) = parser.parse_args()

    if not options.username:
        options.username = input("Enter your username: ")

    if not options.password and not options.offline:
        options.password = getpass.getpass("Enter your password (leave "
                                           "blank for offline mode): ")
        options.offline = options.offline or (options.password == "")

    if not options.server:
        options.server = input("Enter server host or host:port "
                               "(enclose IPv6 addresses in square brackets): ")
    # Try to split out port and address
    match = re.match(r"((?P<host>[^\[\]:]+)|\[(?P<addr>[^\[\]]+)\])"
                     r"(:(?P<port>\d+))?$", options.server)
    if match is None:
        raise ValueError("Invalid server address: '%s'." % options.server)
    options.address = match.group("host") or match.group("addr")
    options.port = int(match.group("port") or 25565)

    return options


def printRawText(json_data):
    if "extra" in json_data:
        for json in json_data["extra"]:
            printRawText(json)

    if "text" in json_data:
        print(json_data["text"], end="")


def printColorText(json_data):
    if "extra" in json_data:
        for json in json_data["extra"]:
            printColorText(json)

    if "text" in json_data:
        text = json_data["text"]
        color_ctrl = None
        if "color" in json_data:
            color = json_data["color"]
            if color in Colors.colors:
                color_ctrl = Colors.colors[color]

        if color_ctrl is None:
            print(text, end="")
        else:
            print(color_ctrl, text, Colors.reset, end="")


def main():
    options = get_options()

    if options.offline:
        print("Connecting in offline mode...")
        connection = Connection(
            options.address, options.port, username=options.username)
    else:
        auth_token = authentication.AuthenticationToken()
        try:
            auth_token.authenticate(options.username, options.password)
        except YggdrasilError as e:
            print(e)
            sys.exit()
        print("Logged in as %s..." % auth_token.username)
        connection = Connection(
            options.address, options.port, auth_token=auth_token)

    if options.dump_packets:
        def print_incoming(packet):
            if type(packet) is Packet:
                # This is a direct instance of the base Packet type, meaning
                # that it is a packet of unknown type, so we do not print it.
                return
            print('--> %s' % packet, file=sys.stderr)

        def print_outgoing(packet):
            print('<-- %s' % packet, file=sys.stderr)

        connection.register_packet_listener(
            print_incoming, Packet, early=True)
        connection.register_packet_listener(
            print_outgoing, Packet, outgoing=True)

    def handle_join_game(join_game_packet):
        print('Connected.')

    connection.register_packet_listener(
        handle_join_game, clientbound.play.JoinGamePacket)

    def print_raw_json(chat_packet):
        print("Message (%s): %s" % (
            chat_packet.field_string('position'), chat_packet.json_data))

    def print_raw_text(chat_packet):
        print("Message (%s): " % 
            chat_packet.field_string('position'), end="")
        printRawText(json.loads(chat_packet.json_data))
        print("")

    def print_color_text(chat_packet):
        print("Message (%s): " % 
            chat_packet.field_string('position'), end="")
        printColorText(json.loads(chat_packet.json_data))
        print("")

    def keep_alive(packet):
        print("keep_alive[%d] packet receive." % packet.keep_alive_id)
        from random import randint
        ret = serverbound.play.KeepAlivePacket()
        ret.keep_alive_id = randint(0, 10000) 
        connection.write_packet(ret)
        print("Write packet ok.")

    connection.register_packet_listener(
        print_color_text, clientbound.play.ChatMessagePacket)
    connection.register_packet_listener(
        keep_alive, clientbound.play.KeepAlivePacket)

    connection.connect()

    while True:
        try:
            text = input()
            if text == "/respawn":
                print("respawning...")
                packet = serverbound.play.ClientStatusPacket()
                packet.action_id = serverbound.play.ClientStatusPacket.RESPAWN
                connection.write_packet(packet)
            else:
                packet = serverbound.play.ChatPacket()
                packet.message = text
                connection.write_packet(packet)
        except KeyboardInterrupt:
            print("Bye!")
            sys.exit()


if __name__ == "__main__":
    main()
