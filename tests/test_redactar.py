from dogfood.reporte.redactar import REDACTADO, redactar, verificar_limpio

JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0In0.c2lnbmF0dXJh"


def test_api_key_conocida_en_url():
    t = redactar("GET https://x.io/a?foo=1&k=SECRETO123abc", ["SECRETO123abc"])
    assert "SECRETO123abc" not in t and REDACTADO in t


def test_param_url_token():
    assert "abc" not in redactar("https://x.io/?token=abc&y=2")


def test_set_cookie():
    t = redactar("Set-Cookie: sesion=abcdef; HttpOnly")
    assert "abcdef" not in t and REDACTADO in t


def test_jwt():
    assert JWT not in redactar(f"token {JWT} fin")


def test_emails():
    t = redactar("ana.3@dogfood.test y x@gmail.com")
    assert "ana.3@dogfood.test" in t and "gmail" not in t


def test_ruta_home_y_runs():
    t = redactar("/home/ana/x.png y runs/1/x.png")
    assert "/home" not in t and "runs/1/x.png" in t


def test_verificar_limpio_detecta_sk():
    assert verificar_limpio("clave sk-abcdefgh12345678")
    assert verificar_limpio(redactar("clave sk-abcdefgh12345678")) == []


def test_texto_sin_secretos_identico():
    t = "El usuario pulsó «Guardar» en /ventas y vio 3 filas. Contacto: ana.3@dogfood.test"
    assert redactar(t, ["zzz"]) == t
    assert verificar_limpio(t) == []
