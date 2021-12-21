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

import unittest

from tests.context import Crypto, CryptoKey


class TestCryptoKey(unittest.TestCase):
    def test_crypto_key_default_build(self):
        try:
            key = CryptoKey()
            self.assertTrue(isinstance(key.value, bytes))
        except Exception as e:
            self.fail(f"Could not build eodag.utils.security.CryptoKey object: {e}")

    def test_crypto_key_build_with_str(self):
        try:
            strkey = "test"
            key1 = CryptoKey(strkey=strkey)
            key2 = CryptoKey.from_str(strkey)
            self.assertTrue(isinstance(key1.value, bytes))
            self.assertTrue(isinstance(key2.value, bytes))
            self.assertEqual(key1, key2)
        except Exception as e:
            self.fail(
                f"Could not build eodag.utils.security.CryptoKey object with strkey: {e}"
            )

    def test_crypto_key_build_with_bytes(self):
        try:
            byteskey = b"test"
            key1 = CryptoKey(byteskey=byteskey)
            key2 = CryptoKey.from_bytes(byteskey)
            print(key1.value, key2.value)
            self.assertTrue(isinstance(key1.value, bytes))
            self.assertTrue(isinstance(key2.value, bytes))
            self.assertEqual(key1, key2)
        except Exception as e:
            self.fail(
                f"Could not build eodag.utils.security.CryptoKey object with byteskey: {e}"
            )

    def test_crypto_key_as_str(self):
        try:
            strkey = "test"
            key = CryptoKey(strkey=strkey)
            self.assertTrue(isinstance(key.value, bytes))
            self.assertEqual(key.as_str(), strkey)
        except Exception as e:
            self.fail(
                f"Could not build eodag.utils.security.CryptoKey object with byteskey: {e}"
            )


class TestCrypto(unittest.TestCase):
    def test_crypto_build(self):
        key = CryptoKey()
        strkey = key.as_str()
        crypto1 = Crypto(key=key)
        crypto2 = Crypto.from_key(key)
        crypto3 = Crypto.from_strkey(strkey)
        self.assertTrue(crypto1 == crypto2 == crypto3)
        # When key is None, a new CryptoKey is built
        crypto4 = Crypto()
        crypto5 = Crypto(key=None)
        self.assertIsNotNone(crypto4.key)
        self.assertIsNotNone(crypto5.key)
        # Generating the strkey from CryptoKey
        # is the safe way of creating an strkey
        # or you might get an error with another
        # arbitrary str
        with self.assertRaises(ValueError):
            Crypto.from_strkey("test")

    def test_crypto_encrypt_decrypt(self):
        crypto = Crypto()
        text = "Hello World!"
        encrypted = crypto.encrypt(text)
        decrypted = crypto.decrypt(encrypted)
        self.assertNotEqual(text, encrypted)
        self.assertEqual(text, decrypted)
