import socket
from typing import Type, List
from xml.etree.ElementTree import Element

from nassl._nassl import OpenSSLError

from sslyze.plugins import plugin_base
from sslyze.plugins.plugin_base import PluginScanResult, PluginScanCommand
from sslyze.server_connectivity_info import ServerConnectivityInfo


class SessionRenegotiationScanCommand(PluginScanCommand):
    """Test the server(s) for client-initiated renegotiation and secure renegotiation support.
    """

    @classmethod
    def get_cli_argument(cls) -> str:
        return 'reneg'

    @classmethod
    def get_title(cls) -> str:
        return 'Session Renegotiation'


class SessionRenegotiationPlugin(plugin_base.Plugin):
    """Test the server(s)' implementation of session renegotiation.
    """

    @classmethod
    def get_available_commands(cls) -> List[Type[PluginScanCommand]]:
        return [SessionRenegotiationScanCommand]

    def process_task(
            self,
            server_info: ServerConnectivityInfo,
            scan_command: PluginScanCommand
    ) -> 'SessionRenegotiationScanResult':
        if not isinstance(scan_command, SessionRenegotiationScanCommand):
            raise ValueError('Unexpected scan command')

        accepts_client_renegotiation = self._test_client_renegotiation(server_info)
        supports_secure_renegotiation = self._test_secure_renegotiation(server_info)
        return SessionRenegotiationScanResult(server_info, scan_command, accepts_client_renegotiation,
                                              supports_secure_renegotiation)

    @staticmethod
    def _test_secure_renegotiation(server_info: ServerConnectivityInfo) -> bool:
        """Check whether the server supports secure renegotiation.
        """
        ssl_connection = server_info.get_preconfigured_ssl_connection(should_use_legacy_openssl=True)

        try:
            # Perform the SSL handshake
            ssl_connection.connect()
            supports_secure_renegotiation = ssl_connection.ssl_client.get_secure_renegotiation_support()

        finally:
            ssl_connection.close()

        return supports_secure_renegotiation

    @staticmethod
    def _test_client_renegotiation(server_info: ServerConnectivityInfo) -> bool:
        """Check whether the server honors session renegotiation requests.
        """
        ssl_connection = server_info.get_preconfigured_ssl_connection(should_use_legacy_openssl=True)

        try:
            # Perform the SSL handshake
            ssl_connection.connect()

            try:
                # Let's try to renegotiate
                ssl_connection.ssl_client.do_renegotiate()
                accepts_client_renegotiation = True

            # Errors caused by a server rejecting the renegotiation
            except socket.timeout:
                # This is how Netty rejects a renegotiation - https://github.com/nabla-c0d3/sslyze/issues/114
                    accepts_client_renegotiation = False
            except socket.error as e:
                if 'connection was forcibly closed' in str(e.args):
                    accepts_client_renegotiation = False
                elif 'reset by peer' in str(e.args):
                    accepts_client_renegotiation = False
                elif 'Nassl SSL handshake failed' in str(e.args):
                    accepts_client_renegotiation = False
                else:
                    raise
            except OpenSSLError as e:
                if 'handshake failure' in str(e.args):
                    accepts_client_renegotiation = False
                elif 'no renegotiation' in str(e.args):
                    accepts_client_renegotiation = False
                elif 'tlsv1 unrecognized name' in str(e.args):
                    # Yahoo's very own way of rejecting a renegotiation
                    accepts_client_renegotiation = False
                elif 'tlsv1 alert internal error' in str(e.args):
                    # Jetty server: https://github.com/nabla-c0d3/sslyze/issues/290
                    accepts_client_renegotiation = False
                else:
                    raise

            except ConnectionError:
                accepts_client_renegotiation = False

        finally:
            ssl_connection.close()

        return accepts_client_renegotiation


class SessionRenegotiationScanResult(PluginScanResult):
    """The result of running a SessionRenegotiationScanCommand on a specific server.

    Attributes:
        accepts_client_renegotiation (bool): True if the server honors client-initiated renegotiation attempts.
        supports_secure_renegotiation (bool): True if the server supports secure renegotiation.
    """

    def __init__(
            self,
            server_info: ServerConnectivityInfo,
            scan_command: SessionRenegotiationScanCommand,
            accepts_client_renegotiation: bool,
            supports_secure_renegotiation: bool
    ) -> None:
        super().__init__(server_info, scan_command)
        self.accepts_client_renegotiation = accepts_client_renegotiation
        self.supports_secure_renegotiation = supports_secure_renegotiation

    def as_text(self) -> List[str]:
        result_txt = [self._format_title(self.scan_command.get_title())]

        # Client-initiated reneg
        client_reneg_txt = 'VULNERABLE - Server honors client-initiated renegotiations' \
            if self.accepts_client_renegotiation \
            else 'OK - Rejected'
        result_txt.append(self._format_field('Client-initiated Renegotiation:', client_reneg_txt))

        # Secure reneg
        secure_txt = 'OK - Supported' \
            if self.supports_secure_renegotiation \
            else 'VULNERABLE - Secure renegotiation not supported'
        result_txt.append(self._format_field('Secure Renegotiation:', secure_txt))

        return result_txt

    def as_xml(self) -> Element:
        result_xml = Element(self.scan_command.get_cli_argument(), title=self.scan_command.get_title())
        result_xml.append(Element('sessionRenegotiation',
                                  attrib={'canBeClientInitiated': str(self.accepts_client_renegotiation),
                                          'isSecure': str(self.supports_secure_renegotiation)}))
        return result_xml
