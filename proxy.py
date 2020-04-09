import asyncio
import functools
import logging
import os
import random
import re
from csv import DictReader
from socket import TCP_NODELAY
from time import time
from traceback import print_exc

import changer

REGEX_HOST = re.compile(r'(.+?):([0-9]{1,5})')
REGEX_CONTENT_LENGTH = re.compile(r'\r\nContent-Length: ([0-9]+)\r\n', re.IGNORECASE)
REGEX_CONNECTION = re.compile(r'\r\nConnection: (.+)\r\n', re.IGNORECASE)

clients = {}

with open(os.path.join(os.getcwd(), "session.log"), 'w'):
    pass
logging.basicConfig(level=logging.DEBUG, format='[%(asctime)s] {%(levelname)s} %(message)s',
                    filename=os.path.join(os.getcwd(), "session.log"))  # Set log file
logging.getLogger('asyncio').setLevel(logging.CRITICAL)
logger = logging.getLogger('warp')
logger.setLevel(logging.DEBUG)
verbose = 0  # Debugging variable

special_sites = None
banned_port = None
verbose_option = None  # Global variable


# so that when the proxy checks for updates it will have something to compare with


def edit_check(sites_dictionary, host):
    """
    If returned value is True, then site should be edited.
    """
    try:
        for site in sites_dictionary.keys():
            if sites_dictionary[site]['host'] in host:
                return True
    except Exception as error_text:
        logger.error("Error edit checking site: {0}. Error message: {1}".format(host, error_text))
        return False
    return False


def ban_check(sites_dictionary, host, port, bport):
    """
    If returned variable is True, then everything is alright and the host has passed the check
    """
    try:
        for site in sites_dictionary.keys():
            if sites_dictionary[site]['host'] in host and sites_dictionary[site]['blacklist'] == 'True':
                return False
        if str(bport) == str(port):
            return False
    except Exception as error_text:
        logger.error("Error ban checking site: {0}. Error message: {1}".format(host, error_text))
        return False
    return True


async def check_for_updates():
    try:
        temp_special_sites = dict()
        temp_banned_port = str()
        temp_verbose_level = str()

        with open(os.path.join(os.getcwd(), "sites.csv"), newline='') as csvfile:
            site_reader = DictReader(csvfile)
            for row in site_reader:
                temp_special_sites[row['host']] = dict()
                temp_special_sites[row['host']]['host'] = row['host']
                temp_special_sites[row['host']]['blacklist'] = row['blacklist']
                temp_special_sites[row['host']]['alert_bool'] = row['alert_bool']
                temp_special_sites[row['host']]['words_to_remove'] = row['words_to_remove']
                temp_special_sites[row['host']]['words_to_replace'] = row['words_to_replace']

        with open(os.path.join(os.getcwd(), "options.csv"), newline='') as csvfile:
            site_reader = DictReader(csvfile)
            for row in site_reader:
                temp_banned_port = row['banned_protocol']
                if temp_banned_port == "HTTP (80)":
                    temp_banned_port = "80"
                elif temp_banned_port == "HTTPS (443)":
                    temp_banned_port = "443"
                else:
                    temp_banned_port = "0"

                temp_verbose_level = row['verbose']

    except (FileNotFoundError, TypeError) as error_text:
        logger.error("Proxy encountered an error while checking for updates: {0}".format(error_text))
    else:
        global special_sites, banned_port, verbose_option
        if special_sites != temp_special_sites or banned_port != temp_banned_port or \
                verbose_option != temp_verbose_level:
            if special_sites != temp_special_sites:
                special_sites = temp_special_sites
            if banned_port != temp_banned_port:
                banned_port = temp_banned_port
            if verbose_option != temp_verbose_level:
                verbose_option = temp_verbose_level
            logger.info("Proxy updated successfully")


def accept_client(client_reader, client_writer, *, loop=None):
    ident = hex(id(client_reader))[-6:]
    task = asyncio.ensure_future(process_warp(client_reader, client_writer, loop=loop), loop=loop)
    clients[task] = (client_reader, client_writer)
    started_time = time()

    def client_done(task):
        del clients[task]
        client_writer.close()
        logger.debug('[%s] Connection closed (took %.5f seconds)' % (ident, time() - started_time))

    logger.debug('[%s] Connection started' % ident)
    task.add_done_callback(client_done)


async def process_warp(client_reader, client_writer, *, loop=None):
    global banned_port
    global special_sites
    ident = str(hex(id(client_reader)))[-6:]
    header = ''
    payload = b''
    await check_for_updates()
    try:
        RECV_MAX_RETRY = 3
        recvRetry = 0
        while True:
            line = await client_reader.readline()
            if not line:
                if len(header) == 0 and recvRetry < RECV_MAX_RETRY:
                    # handle the case when the client make connection but sending data is delayed for some reasons
                    recvRetry += 1
                    await asyncio.sleep(0.2, loop=loop)  # delay
                    continue
                else:
                    break
            if line == b'\r\n':
                break
            if line != b'':  # If there is data
                header += line.decode()  # HTTP HEADER

        m = REGEX_CONTENT_LENGTH.search(header)  # With regular expressions, search for the length

        if m:
            cl = int(m.group(1))
            while len(payload) < cl:
                payload += await client_reader.read(1024)  # Use Generators  = less time and resources
    except:
        print_exc()  # if there is a failure with

    if len(header) == 0:
        logger.debug('[%s] !!! Task reject (empty request)' % ident)  # Add to Log
        return

    req = header.split('\r\n')[:-1]
    if len(req) < 4:
        logger.debug('[%s] !!! Task reject (invalid request)' % ident)  # Add to Log
        return
    head = req[0].split(' ')
    if head[0] == 'CONNECT':  # https proxy
        try:
            logger.info('%sBYPASSING <%s %s> (SSL connection)' %
                        ('[%s] ' % ident if verbose >= 1 else '', head[0], head[1]))

            m = REGEX_HOST.search(head[1])
            host = m.group(1)
            port = int(m.group(2))

            if ban_check(special_sites, host, port, banned_port):  # If message should be banned
                req_reader, req_writer = await asyncio.open_connection(host, port, ssl=False, loop=loop)
                client_writer.write(b'HTTP/1.1 200 Connection established\r\n\r\n')

                async def relay_stream(reader, writer):
                    try:
                        while True:
                            line = await reader.read(1024)
                            if len(line) == 0:
                                break
                            writer.write(line)
                    except ConnectionResetError:
                        logger.info("Connection Aborted")
                    except:
                        print_exc()

                tasks = [
                    asyncio.ensure_future(relay_stream(client_reader, req_writer), loop=loop),
                    asyncio.ensure_future(relay_stream(req_reader, client_writer), loop=loop),
                ]
                await asyncio.wait(tasks, loop=loop)
            else:
                logger.info("Blocking message from host: {0}".format(host))
        except:
            print_exc()
        finally:
            return

    phost = False  # host's port
    sreq = []  # https request
    sreqHeaderEndIndex = 0  # https end of header index

    for line in req[1:]:  # for every line in the request
        headerNameAndValue = line.split(': ', 1)
        if len(headerNameAndValue) == 2:
            headerName, headerValue = headerNameAndValue
        else:
            headerName, headerValue = headerNameAndValue[0], None

        if headerName.lower() == "host":
            phost = headerValue
        elif headerName.lower() == "connection":
            if headerValue.lower() in ('keep-alive', 'persist'):
                # current version of this program does not support the HTTP keep-alive feature
                sreq.append("Connection: close")
            else:
                sreq.append(line)
        elif headerName.lower() != 'proxy-connection':
            sreq.append(line)
            if len(line) == 0 and sreqHeaderEndIndex == 0:
                sreqHeaderEndIndex = len(sreq) - 1
    if sreqHeaderEndIndex == 0:
        sreqHeaderEndIndex = len(sreq)

    m = REGEX_CONNECTION.search(header)
    if not m:
        sreq.insert(sreqHeaderEndIndex, "Connection: close")

    if not phost:
        phost = '127.0.0.1'
    path = head[1][len(phost) + 7:]

    logger.info('%sWARPING <%s %s>' % ('[%s] ' % ident if verbose >= 1 else '', head[0], head[1]))

    new_head = ' '.join([head[0], path, head[2]])

    m = REGEX_HOST.search(phost)
    if m:
        host = m.group(1)
        port = int(m.group(2))
    else:
        host = phost
        port = 80

    if ban_check(special_sites, host, port, banned_port):
        try:  # For HTTP
            req_reader, req_writer = await asyncio.open_connection(host, port, flags=TCP_NODELAY, loop=loop)
            req_writer.write(('%s\r\n' % new_head).encode())
            await req_writer.drain()
            await asyncio.sleep(0.2, loop=loop)

            def generate_dummyheaders():
                def generate_rndstrs(strings, length):
                    return ''.join(random.choice(strings) for _ in range(length))

                import string
                return ['X-%s: %s\r\n' % (generate_rndstrs(string.ascii_uppercase, 16),
                                          generate_rndstrs(string.ascii_letters + string.digits, 128)) for _ in
                        range(32)]

            req_writer.writelines(list(map(lambda x: x.encode(), generate_dummyheaders())))
            await req_writer.drain()

            req_writer.write(b'Host: ')
            await req_writer.drain()

            def feed_phost(phost):
                i = 1
                while phost:
                    yield random.randrange(2, 4), phost[:i]
                    phost = phost[i:]
                    i = random.randrange(2, 5)

            for delay, c in feed_phost(phost):
                await asyncio.sleep(delay / 10.0, loop=loop)
                req_writer.write(c.encode())
                await req_writer.drain()
            req_writer.write(b'\r\n')
            req_writer.writelines(list(map(lambda x: (x + '\r\n').encode(), sreq)))
            req_writer.write(b'\r\n')
            if payload != b'':
                req_writer.write(payload)
                await req_writer.drain()

            try:
                data = b''
                if not data:
                    data = b''

                    while True:
                        buf = await req_reader.read(1024)
                        if len(buf) == 0:
                            break
                        data += buf
                        # /End

                    if edit_check(special_sites, host):
                        logger.info("{0} appears to be wanted edited".format(host))
                        changer_object = changer.Changer(data)

                        for site in special_sites.keys():
                            if special_sites[site]['host'] in host:
                                specials = special_sites[site]
                            else:
                                specials = {'words_to_replace': 'None',
                                            'words_to_remove': 'None',
                                            'alert_bool': 'None'}

                        if specials['words_to_replace'] != '':
                            words_to_replace = dict()
                            separated_words = specials['words_to_replace'].split(',')
                            for word in separated_words:
                                words_to_replace[word.split(':')[0]] = word.split(':')[1]
                            changer_object.set_words_to_replace(words_to_replace)

                        if specials['words_to_remove'] != '':
                            words_to_remove = specials['words_to_remove'].split(',')
                            changer_object.set_words_to_remove(words_to_remove)

                        print("{0} == {1}".format(specials['alert_bool'], type(specials['alert_bool'])))
                        if "True" in specials['alert_bool']:
                            changer_object.set_alert_bool(specials['alert_bool'])

                        changer_object.perform_changes()
                        data = changer_object.get_http_message()  # bytes data / encoded

                client_writer.write(data)

            except:
                print_exc()

        except:
            print_exc()
    else:
        logger.info("Blocking message from host: {0}".format(host))

    client_writer.close()


async def start_warp_server(host, port, *, loop=None):
    try:
        accept = functools.partial(accept_client, loop=loop)
        server = await asyncio.start_server(accept, host=host, port=port, loop=loop)
    except OSError as e:
        logger.critical('!!! Failed to bind server at [%s:%d]: %s' % (host, port, e.args[1]))
        raise
    else:
        logger.debug('Server bound at [%s:%d].' % (host, port))
        return server


def main(verbose_level, ip, port, bport, special, loop=asyncio.get_event_loop()):
    global verbose_option
    verbose_option = verbose_level
    if verbose_level == "info":
        logger.setLevel(logging.INFO)
    elif verbose_level == "error":
        logger.setLevel(logging.ERROR)
    else:
        logger.setLevel(logging.DEBUG)
    global special_sites
    special_sites = special if special is not None else None
    global banned_port
    if bport == "HTTP (80)":
        banned_port = "80"
    elif bport == "HTTPS (443)":
        banned_port = "443"
    else:
        banned_port = "0"

    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(start_warp_server(ip, int(port)))
        loop.run_forever()
    except OSError as error_text:
        logger.error("Proxy OS error: {0}".format(error_text))
    except KeyboardInterrupt:
        logger.error("Proxy Closed")
    finally:
        loop.close()


if __name__ == '__main__':
    pass
