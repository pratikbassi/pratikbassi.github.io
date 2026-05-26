/**
 * Private gallery gate: SHA-256 auth cookie + AES decryption key cookie.
 * Change AUTH_TOKEN after updating the password (see scripts/gen_private_token.py).
 */
(function (window) {
    "use strict";

    var COOKIE_NAME = "pb_private_auth";
    var KEY_COOKIE_NAME = "pb_private_key";
    var COOKIE_MAX_AGE_DAYS = 30;

    // SHA-256("pratik-private-v1:<password>") — generate with scripts/gen_private_token.py
    var AUTH_TOKEN = "7728862ac581e3fa24c610a0179b27ae54dffd9c54a0f1ab3018a88e568d442c";
    var AUTH_SALT = "pratik-private-v1";

    var pendingCallbacks = [];
    var gateEl;
    var galleryEl;
    var formEl;
    var inputEl;
    var errorEl;

    function getCookie(name) {
        var parts = document.cookie ? document.cookie.split(";") : [];
        var i;
        for (i = 0; i < parts.length; i++) {
            var part = parts[i].replace(/^\s+/, "");
            if (part.indexOf(name + "=") === 0) {
                return decodeURIComponent(part.substring(name.length + 1));
            }
        }
        return null;
    }

    function setCookie(name, value) {
        var maxAge = COOKIE_MAX_AGE_DAYS * 24 * 60 * 60;
        var secure = window.location.protocol === "https:" ? "; Secure" : "";
        document.cookie =
            name +
            "=" +
            encodeURIComponent(value) +
            "; Path=/; Max-Age=" +
            maxAge +
            "; SameSite=Lax" +
            secure;
    }

    function clearCookie(name) {
        document.cookie = name + "=; Path=/; Max-Age=0; SameSite=Lax";
    }

    function setAuthCookie(token) {
        setCookie(COOKIE_NAME, token);
    }

    function clearAuthCookies() {
        clearCookie(COOKIE_NAME);
        clearCookie(KEY_COOKIE_NAME);
        if (window.PrivateCrypto) {
            PrivateCrypto.setCryptoKey(null);
        }
    }

    function hashPassword(password) {
        // Must match scripts/gen_private_token.py: SHA-256(f"{salt}:{password}")
        var data = new TextEncoder().encode(AUTH_SALT + ":" + password);
        return window.crypto.subtle.digest("SHA-256", data).then(function (buffer) {
            var bytes = new Uint8Array(buffer);
            var hex = "";
            var i;
            for (i = 0; i < bytes.length; i++) {
                hex += bytes[i].toString(16).padStart(2, "0");
            }
            return hex;
        });
    }

    function isAuthenticated() {
        return getCookie(COOKIE_NAME) === AUTH_TOKEN;
    }

    function unlockGallery() {
        if (gateEl) {
            gateEl.style.display = "none";
        }
        if (galleryEl) {
            galleryEl.classList.remove("gallery-app--locked");
            galleryEl.removeAttribute("aria-hidden");
        }
        document.body.classList.remove("private-locked");

        while (pendingCallbacks.length) {
            pendingCallbacks.shift()();
        }
    }

    function showGate() {
        if (gateEl) {
            gateEl.style.display = "flex";
        }
        if (galleryEl) {
            galleryEl.classList.add("gallery-app--locked");
            galleryEl.setAttribute("aria-hidden", "true");
        }
        document.body.classList.add("private-locked");
    }

    function establishSession(password) {
        if (!window.crypto || !window.crypto.subtle) {
            return Promise.reject(new Error("Web Crypto requires HTTPS or localhost"));
        }
        if (!window.PrivateCrypto) {
            return Promise.reject(new Error("private-crypto.js failed to load"));
        }
        return hashPassword(password).then(function (digest) {
            if (digest !== AUTH_TOKEN) {
                return false;
            }
            return PrivateCrypto.deriveCryptoKey(password).then(function (cryptoKey) {
                return PrivateCrypto.exportKeyToBase64(cryptoKey).then(function (keyB64) {
                    PrivateCrypto.setCryptoKey(cryptoKey);
                    setAuthCookie(AUTH_TOKEN);
                    setCookie(KEY_COOKIE_NAME, keyB64);
                    return true;
                });
            });
        });
    }

    function restoreSessionFromCookies() {
        if (!isAuthenticated()) {
            return Promise.resolve(false);
        }
        var keyB64 = getCookie(KEY_COOKIE_NAME);
        if (!keyB64 || !window.PrivateCrypto) {
            clearAuthCookies();
            return Promise.resolve(false);
        }
        return PrivateCrypto.importKeyFromBase64(keyB64).then(function (cryptoKey) {
            PrivateCrypto.setCryptoKey(cryptoKey);
            return true;
        }).catch(function () {
            clearAuthCookies();
            return false;
        });
    }

    function onSubmit(event) {
        event.preventDefault();
        if (!inputEl) {
            return;
        }

        var password = inputEl.value.trim();
        errorEl.textContent = "";

        establishSession(password).then(function (ok) {
            if (ok) {
                inputEl.value = "";
                unlockGallery();
                return;
            }
            errorEl.textContent = "Incorrect password.";
            inputEl.focus();
        }).catch(function (err) {
            console.error("Private gate:", err);
            if (err && err.message && err.message.indexOf("HTTPS") !== -1) {
                errorEl.textContent = "This page must be served over HTTP(S), not opened as a file.";
            } else {
                errorEl.textContent = "Could not unlock gallery.";
            }
        });
    }

    function bindGateUi() {
        gateEl = document.getElementById("privateGate");
        galleryEl = document.getElementById("galleryApp");
        formEl = document.getElementById("privateGateForm");
        inputEl = document.getElementById("privateGatePassword");
        errorEl = document.getElementById("privateGateError");

        if (formEl) {
            formEl.addEventListener("submit", onSubmit);
        }
    }

    function ensureReady() {
        if (!isAuthenticated()) {
            return Promise.resolve(false);
        }
        if (window.PrivateCrypto && PrivateCrypto.hasCryptoKey()) {
            return Promise.resolve(true);
        }
        return restoreSessionFromCookies();
    }

    function whenAuthenticated(callback) {
        ensureReady().then(function (ready) {
            if (ready) {
                callback();
            } else {
                pendingCallbacks.push(callback);
            }
        });
    }

    function decryptToObjectUrl(path) {
        return ensureReady().then(function (ready) {
            if (!ready) {
                return Promise.reject(new Error("Not authenticated"));
            }
            return PrivateCrypto.decryptToObjectUrl(path);
        });
    }

    function init() {
        bindGateUi();
        restoreSessionFromCookies().then(function (ready) {
            if (ready) {
                unlockGallery();
            } else {
                showGate();
            }
        });
    }

    window.PrivateGate = {
        isAuthenticated: isAuthenticated,
        whenAuthenticated: whenAuthenticated,
        clearAuth: clearAuthCookies,
        decryptToObjectUrl: decryptToObjectUrl,
        init: init,
    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})(window);
