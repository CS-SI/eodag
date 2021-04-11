.. module:: eodag.plugins.authentication

======================
Authentication Plugins
======================

Authentication plugins must inherit the following class and implement :meth:`authenticate`:

.. autoclass:: eodag.plugins.authentication.base.Authentication
   :members:

This table lists all the authentication plugins currently available:

.. autosummary::
   :toctree: generated/

   eodag.plugins.authentication.generic.GenericAuth
   eodag.plugins.authentication.token.TokenAuth
   eodag.plugins.authentication.header.HTTPHeaderAuth
   eodag.plugins.authentication.aws_auth.AwsAuth
   eodag.plugins.authentication.oauth.OAuth
   eodag.plugins.authentication.openid_connect.OIDCAuthorizationCodeFlowAuth
   eodag.plugins.authentication.keycloak.KeycloakOIDCPasswordAuth
