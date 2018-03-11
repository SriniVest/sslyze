from __future__ import absolute_import
from __future__ import unicode_literals

from typing import Text, Optional

from nassl.ssl_client import OpenSslVersionEnum

from sslyze.ssl_settings import TlsWrappedProtocolEnum, ClientAuthenticationCredentials, HttpConnectTunnelingSettings, \
    ClientAuthenticationServerConfigurationEnum
from sslyze.utils.ssl_connection import SSLConnection
from sslyze.utils.ssl_connection_configurator import SslConnectionConfigurator


class ServerConnectivityInfo(object):
    """All the settings (hostname, port, SSL version, etc.) needed to successfully connect to a given SSL/TLS server.

    Such objects are returned by `ServerConnectivityTester.perform()` if connectivity testing was successful, and should
    never be instantiated directly.

    Attributes:
        hostname (Text): The server's hostname.
        port (int): The server's TLS port number.
        ip_address (Text): The server's IP address.
        tls_wrapped_protocol (TlsWrappedProtocolEnum): The protocol wrapped in TLS (HTTP, XMPP, etc.) that the server
            expects.
        tls_server_name_indication (Text): The hostname to set within the Server Name Indication TLS extension.
        xmpp_to_hostname (Optional[Text]): The hostname to set within the `to` attribute of the XMPP stream; only used
            if the `tls_wrapped_protocol` is an XMPP protocol.
        client_auth_credentials (Optional[ClientAuthenticationCredentials]): The client certificate and private key
            needed to perform mutual authentication with the server. If not supplied, SSLyze will attempt to connect
            to the server without performing mutual authentication.
        http_tunneling_settings (Optional[HttpConnectTunnelingSettings]): The HTTP proxy configuration to use in
            order to tunnel the scans through a proxy. If not supplied, SSLyze will run the scans by directly
            connecting to the server.
        highest_ssl_version_supported (OpenSslVersionEnum): The highest version of SSL/TLS supported by the server, as
            detected when doing connectivity testing.
        openssl_cipher_string_supported (Text): An OpenSSL cipher string that contains at least one cipher suite
            supported by the server, as detected when doing connectivity testing.
        client_auth_requirement (ClientAuthenticationServerConfigurationEnum): Whether the support requires client
            authentication.
    """

    def __init__(
            self,
            hostname,                                               # type: Text
            port,                                                   # type: int
            ip_address,                                             # type: Text
            tls_wrapped_protocol,                                   # type: TlsWrappedProtocolEnum
            tls_server_name_indication,                             # type: Text
            xmpp_to_hostname,                                       # type: Optional[Text]
            client_auth_credentials,                                # type: Optional[ClientAuthenticationCredentials]
            http_tunneling_settings,                                # type: Optional[HttpConnectTunnelingSettings]
            highest_ssl_version_supported,                          # type: OpenSslVersionEnum
            openssl_cipher_string_supported,                        # type: Text
            client_auth_requirement,                                # type: ClientAuthenticationServerConfigurationEnum
            ):
        # type: (...) -> None
        self.hostname = hostname
        self.port = port
        self.ip_address = ip_address
        self.tls_wrapped_protocol = tls_wrapped_protocol
        self.tls_server_name_indication = tls_server_name_indication
        self.xmpp_to_hostname = xmpp_to_hostname
        self.client_auth_credentials = client_auth_credentials
        self.http_tunneling_settings = http_tunneling_settings

        # Settings validated via connectivity testing
        self.highest_ssl_version_supported = highest_ssl_version_supported
        self.openssl_cipher_string_supported = openssl_cipher_string_supported
        self.client_auth_requirement = client_auth_requirement

    def get_preconfigured_ssl_connection(
            self,
            override_ssl_version=None,          # type: Optional[OpenSslVersionEnum]
            ssl_verify_locations=None,          # type: Optional[Text]
            should_use_legacy_openssl=None,     # type: Optional[bool]
    ):
        # type: (...) -> SSLConnection
        """Get an SSLConnection instance with the right SSL configuration for successfully connecting to the server.

        Used by all plugins to connect to the server and run scans.
        """
        if override_ssl_version is not None:
            # Caller wants to override the ssl version to use for this connection
            final_ssl_version = override_ssl_version
            # Then we don't know which cipher suite is supported by the server for this ssl version
            openssl_cipher_string = None
        else:
            # Use the ssl version and cipher suite that were successful during connectivity testing
            final_ssl_version = self.highest_ssl_version_supported
            openssl_cipher_string = self.openssl_cipher_string_supported

        if should_use_legacy_openssl is not None:
            # Caller wants to override which version of OpenSSL to use
            # Then we don't know which cipher suite is supported by this version of OpenSSL
            openssl_cipher_string = None

        if self.client_auth_credentials is not None:
            # If we have creds for client authentication, go ahead and use them
            should_ignore_client_auth = False
        else:
            # Ignore client auth requests if the server allows optional TLS client authentication
            should_ignore_client_auth = True
            # But do not ignore them is client authentication is required so that the right exceptions get thrown
            # within the plugins, providing a better output
            if self.client_auth_requirement == ClientAuthenticationServerConfigurationEnum.REQUIRED:
                should_ignore_client_auth = False

        ssl_connection = SslConnectionConfigurator.get_connection(
            ssl_version=final_ssl_version,
            server_info=self,
            openssl_cipher_string=openssl_cipher_string,
            ssl_verify_locations=ssl_verify_locations,
            should_use_legacy_openssl=should_use_legacy_openssl,
            should_ignore_client_auth=should_ignore_client_auth,
        )
        return ssl_connection

    def __str__(self):
        # type: () -> Text
        return '<{class_name}: server=({hostname}, {ip_addr}, {port})>'.format(
            class_name=self.__class__.__name__,
            hostname=self.hostname,
            ip_addr=self.ip_address,
            port=self.port,
        )