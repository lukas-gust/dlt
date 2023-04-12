from typing import Any, ClassVar, Final, List, Optional
from dlt.common import json
from dlt.common.configuration.specs.exceptions import InvalidServicesJson
from dlt.common.exceptions import MissingDependencyException
from dlt.common.typing import TSecretValue
from dlt.common.configuration.specs.base_configuration import CredentialsConfiguration, CredentialsWithDefault, configspec


@configspec
class GcpCredentialsBase(CredentialsConfiguration):
    project_id: str = None
    location: str = "US"
    token_uri: Final[str] = "https://oauth2.googleapis.com/token"
    http_timeout: float = 15.0
    file_upload_timeout: float = 30 * 60.0
    retry_deadline: float = 60  # how long to retry the operation in case of error, the backoff 60s
    __config_gen_annotations__: ClassVar[List[str]] = ["location"]

    def parse_native_representation(self, native_value: Any) -> None:
        if not isinstance(native_value, str):
            raise InvalidServicesJson(self.__class__, native_value)
        try:
            service_dict = json.loads(native_value)
            self.update(service_dict)
            self.__is_resolved__ = not self.is_partial()
        except Exception:
            raise InvalidServicesJson(self.__class__, native_value)

    def to_native_representation(self) -> str:
        return json.dumps(dict(self))

    def __str__(self) -> str:
        return f"{self.project_id}[{self.location}]"


@configspec
class GcpClientCredentials(GcpCredentialsBase):
    private_key: TSecretValue = None
    client_email: str = None
    type: Final[str] = "service_account"  # noqa: A003

    def on_resolved(self) -> None:
        if self.private_key and self.private_key[-1] != "\n":
            # must end with new line, otherwise won't be parsed by Crypto
            self.private_key = TSecretValue(self.private_key + "\n")

    def to_service_account_credentials(self) -> Any:
        from google.oauth2 import service_account
        return service_account.Credentials.from_service_account_info(self)

    def __str__(self) -> str:
        return f"{self.client_email}@{self.project_id}[{self.location}]"


@configspec
class GcpClientCredentialsWithDefault(CredentialsWithDefault, GcpClientCredentials):

    def on_partial(self) -> None:
        try:
            from google.auth import default as default_credentials
            from google.auth.exceptions import DefaultCredentialsError

            # if config is missing check if credentials can be obtained from defaults
            try:
                default, project_id = default_credentials()
                # set the project id - it needs to be known by the client
                self.project_id = self.project_id or project_id
                self._set_default_credentials(default)
                # is resolved
                self.__is_resolved__ = True
            except DefaultCredentialsError:
                # re-raise preventing exception
                raise self.__exception__

        except ImportError:
            raise self.__exception__

    def to_service_account_credentials(self) -> Any:
        if self.has_default_credentials():
            return self.default_credentials()
        else:
            return super().to_service_account_credentials()


@configspec
class GcpOAuthCredentials(GcpCredentialsBase):
    client_id: str
    client_secret: TSecretValue
    project_id: TSecretValue
    refresh_token: TSecretValue
    access_token: Optional[TSecretValue] = None

    def auth(self, scope: str, redirect_uri: str) -> None:
        """
        Will produce an access token from the given credentials.
        :param scope: The scope of oauth token permissions, must match the scope of the refresh tokens.
        :param redirect_uri: The redirect uri specified in the oauth client.
        :return: None
        """
        try:
            from requests_oauthlib import OAuth2Session
        except ImportError:
            raise MissingDependencyException("Requests-OAuthlib", ["requests_oauthlib"])
        try:
            google = OAuth2Session(client_id=self.client_id, scope=scope, redirect_uri=redirect_uri)
            extra = {
                "client_id": self.client_id,
                "client_secret": self.client_secret
            }
            self.access_token = google.refresh_token(token_url=self.token_uri, refresh_token=self.refresh_token, **extra)["access_token"]
        except Exception:
            raise ValueError("Invalid credentials for creating an OAuth token!")

    def to_google_credentials(self) -> Any:
        """
        Will convert the object to a Google oauth2 credentials object
        :returns: Google Credentials object
        """
        try:
            from google.oauth2.credentials import Credentials
        except ImportError:
            raise MissingDependencyException("Google OAuth Library", ["google-auth-oauthlib"])

        credentials = Credentials.from_authorized_user_info(info={
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "token": self.access_token
        })
        return credentials
