# -*- coding: utf-8 -*-
# Copyright 2021, CS GROUP - France, https://www.csgroup.eu/
#
# This file is part of EODAG project
#     https://www.github.com/CS-SI/EODAG
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from cryptography.fernet import Fernet


class CryptoKey:
    """Encapsulate a key implementation."""

    def __init__(self, strkey=None, byteskey=None):
        if strkey:
            self._value = strkey.encode()
        elif byteskey:
            self._value = byteskey
        else:
            self._value = Fernet.generate_key()

    @staticmethod
    def from_str(strkey):
        """Build a :class:`~eodag.utils.security.CryptoKey` object from its string representation

        :param strkey: The key as str
        :type strkey: str
        :returns: The :class:`~eodag.utils.security.CryptoKey` built from `strkey`
        :rtype: :class:`~eodag.utils.security.CryptoKey`
        """
        return CryptoKey(strkey=strkey)

    @staticmethod
    def from_bytes(byteskey):
        """Build a :class:`~eodag.utils.security.CryptoKey` object from its bytes representation

        :param byteskey: The key as bytes
        :type byteskey: bytes
        :returns: The :class:`~eodag.utils.security.CryptoKey` built from `byteskey`
        :rtype: :class:`~eodag.utils.security.CryptoKey`
        """
        return CryptoKey(byteskey=byteskey)

    @property
    def value(self):
        """Read-only property on the value of the key"""
        return self._value

    def as_str(self):
        """Return str representation of the key"""
        return self.value.decode()

    def __eq__(self, other: "CryptoKey") -> bool:
        return isinstance(other, CryptoKey) and self.value == other.value


class Crypto:
    """Class used for symmetric encryption of text, using a key."""

    def __init__(self, key=None):
        self._key = key if key is not None else CryptoKey()
        self._impl = Fernet(self._key.value)

    @staticmethod
    def from_key(key):
        """Build a :class:`~eodag.utils.security.Crypto` object with a :class:`~eodag.utils.security.CryptoKey`

        :param key: The key as str
        :type key: :class:`~eodag.utils.security.CryptoKey`
        :returns: The :class:`~eodag.utils.security.Crypto` object built
                  with a :class:`~eodag.utils.security.CryptoKey`
        :rtype: :class:`~eodag.utils.security.Crypto`
        """
        return Crypto(key=key)

    @staticmethod
    def from_strkey(strkey):
        """Build a :class:`~eodag.utils.security.Crypto` object with a key str

        :param strkey: The key as str
        :type strkey: str
        :returns: The :class:`~eodag.utils.security.Crypto` object built
                  with a :class:`~eodag.utils.security.CryptoKey`, itself built from `strkey`
        :rtype: :class:`~eodag.utils.security.Crypto`
        """
        key = CryptoKey.from_str(strkey=strkey)
        return Crypto.from_key(key=key)

    @property
    def key(self):
        """Read-only property on the key used by the :class:`~eodag.utils.security.Crypto` object"""
        return self._key

    def encrypt(self, text):
        """Encrypt a text

        :param text: The text to encrypt
        :type text: str
        :returns: The encrypted text
        :rtype: str
        """
        return self._impl.encrypt(text.encode()).decode()

    def decrypt(self, encrypted_text):
        """Decrypt an encrypted text

        :param encrypted_text: The encrypted text
        :type encrypted_text: str
        :returns: The decrypted text
        :rtype: str
        """
        return self._impl.decrypt(encrypted_text.encode()).decode()

    def __eq__(self, other: "Crypto") -> bool:
        return isinstance(other, Crypto) and self.key == other.key
