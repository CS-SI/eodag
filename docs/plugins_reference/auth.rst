.. module:: eodag.plugins.authentication

======================
Authentication Plugins
======================

Multiple authentication plugins can be defined per provider under ``auth``, ``search_auth``, or ``download_auth``
`provider configuration entries <../add_provider.rst>`_. They are shared across all providers, and can be identified
using *matching settings* :attr:`~eodag.config.PluginConfig.matching_url` and
:attr:`~eodag.config.PluginConfig.matching_conf` as configuration parameters.
Credentials are automatically shared between plugins having the same *matching settings*.
Authentication plugins without *matching settings* configured will not be shared and will automatically match their
provider.

Authentication plugins must inherit the following class and implement :meth:`authenticate`:

.. autoclass:: eodag.plugins.authentication.base.Authentication
   :members:

This table lists all the authentication plugins currently available:

.. autosummary::
   :toctree: generated/

   generic.GenericAuth
   token.TokenAuth
   header.HTTPHeaderAuth
   aws_auth.AwsAuth
   oauth.OAuth
   openid_connect.OIDCRefreshTokenBase
   openid_connect.OIDCAuthorizationCodeFlowAuth
   keycloak.KeycloakOIDCPasswordAuth
   token_exchange.OIDCTokenExchangeAuth
   qsauth.HttpQueryStringAuth
   sas_auth.SASAuth
