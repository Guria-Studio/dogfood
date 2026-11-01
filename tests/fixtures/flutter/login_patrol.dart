import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:patrol/patrol.dart';

import 'package:app/main.dart' as app;

void main() {
  patrolTest('Iniciar sesión (determinista)', ($) async {
    app.main();
    await $.pumpAndSettle();
    await $(#campo_email).enterText(const String.fromEnvironment('DOGFOOD_APP_EMAIL'));
    await $(#campo_contrasena).enterText(const String.fromEnvironment('DOGFOOD_APP_CONTRASENA'));
    await $(#boton_entrar).tap();
    await $('Início').waitUntilVisible(timeout: Duration(milliseconds: 20000));
  });
}
