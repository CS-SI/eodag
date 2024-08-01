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

   generic.GenericAuth
   token.TokenAuth
   header.HTTPHeaderAuth
   aws_auth.AwsAuth
   oauth.OAuth
   openid_connect.OIDCAuthorizationCodeFlowAuth
   keycloak.KeycloakOIDCPasswordAuth
   qsauth.HttpQueryStringAuth
   sas_auth.SASAuth
