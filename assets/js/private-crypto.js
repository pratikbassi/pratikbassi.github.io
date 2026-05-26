/**
 * Decrypt private gallery .enc files (must match scripts/private_crypto.py).
 */
(function (window) {
    "use strict";

    var ENC_SALT = "pratik-private-enc-v1";
    var PBKDF2_ITERATIONS = 100000;
    var _cryptoKey = null;
    var _urlCache = {};

    function importRawKey(rawBytes) {
        return window.crypto.subtle.importKey(
            "raw",
            rawBytes,
            { name: "AES-GCM", length: 256 },
            false,
            ["decrypt"]
        );
    }

    function deriveCryptoKey(password) {
        var enc = new TextEncoder();
        return window.crypto.subtle
            .importKey("raw", enc.encode(password), "PBKDF2", false, ["deriveKey"])
            .then(function (keyMaterial) {
                return window.crypto.subtle.deriveKey(
                    {
                        name: "PBKDF2",
                        salt: enc.encode(ENC_SALT),
                        iterations: PBKDF2_ITERATIONS,
                        hash: "SHA-256",
                    },
                    keyMaterial,
                    { name: "AES-GCM", length: 256 },
                    true,
                    ["decrypt"]
                );
            });
    }

    function exportKeyToBase64(cryptoKey) {
        return window.crypto.subtle.exportKey("raw", cryptoKey).then(function (raw) {
            var bytes = new Uint8Array(raw);
            var binary = "";
            var i;
            for (i = 0; i < bytes.length; i++) {
                binary += String.fromCharCode(bytes[i]);
            }
            return btoa(binary);
        });
    }

    function importKeyFromBase64(b64) {
        var binary = atob(b64);
        var bytes = new Uint8Array(binary.length);
        var i;
        for (i = 0; i < binary.length; i++) {
            bytes[i] = binary.charCodeAt(i);
        }
        return importRawKey(bytes);
    }

    function setCryptoKey(cryptoKey) {
        _cryptoKey = cryptoKey;
        _urlCache = {};
    }

    function hasCryptoKey() {
        return _cryptoKey !== null;
    }

    function decryptToObjectUrl(path) {
        if (!_cryptoKey) {
            return Promise.reject(new Error("Private gallery key not loaded"));
        }
        if (_urlCache[path]) {
            return Promise.resolve(_urlCache[path]);
        }

        return fetch(path)
            .then(function (response) {
                if (!response.ok) {
                    throw new Error("Failed to load " + path);
                }
                return response.arrayBuffer();
            })
            .then(function (buffer) {
                var data = new Uint8Array(buffer);
                var nonce = data.slice(0, 12);
                var ciphertext = data.slice(12);
                return window.crypto.subtle.decrypt(
                    { name: "AES-GCM", iv: nonce },
                    _cryptoKey,
                    ciphertext
                );
            })
            .then(function (decrypted) {
                var blob = new Blob([decrypted], { type: "image/jpeg" });
                var url = URL.createObjectURL(blob);
                _urlCache[path] = url;
                return url;
            });
    }

    window.PrivateCrypto = {
        deriveCryptoKey: deriveCryptoKey,
        exportKeyToBase64: exportKeyToBase64,
        importKeyFromBase64: importKeyFromBase64,
        setCryptoKey: setCryptoKey,
        hasCryptoKey: hasCryptoKey,
        decryptToObjectUrl: decryptToObjectUrl,
    };
})(window);
