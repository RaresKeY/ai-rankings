# CI TLS trust

The workflow configures a reviewed CA bundle before its first HTTPS operation. It contains eleven public roots copied on 2026-10-28 from the workstation's system store, which had passed the eMudhra/emSign incident audit. The source bundle is `/etc/ca-certificates/extracted/tls-ca-bundle.pem`; its audited SHA-256 is `9a9c1b798f6ae057ecb84545704e38c89e10f3db5519b24cd4647a1bb2dbf299`.

Included roots: Sectigo R46 and E46, GTS R1 and R4, Amazon Root CA 1, ISRG X1 and X2, DigiCert Global G2 and G3, GlobalSign R3 and R6. All are public certificates. No private key is present.

The workflow embeds the compressed bundle, verifies its pinned hash and selects it via SSL_CERT_FILE, CURL_CA_BUNDLE, REQUESTS_CA_BUNDLE and GIT_SSL_CAINFO. SSL_CERT_DIR and GIT_SSL_CAPATH point to an empty directory. Pip is never invoked; PIP_CERT is also configured. The runner's unrelated certificate bundles are not used by the workflow's network operations. TLS verification stays enabled.

Verify replacement roots against [the incident advisory](https://discuss.python.org/t/109576) and official CA sources before changing the bundle or its hash. Run `python3 scripts/configure_ci.py` after an authorized, audited update. The hash is an integrity pin, not a substitute for reviewing trust anchors. Certificate chain changes may require maintenance; do not bypass verification to work around a failure.
