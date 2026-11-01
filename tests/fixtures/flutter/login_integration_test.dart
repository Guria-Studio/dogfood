import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

import 'package:app/main.dart' as app;

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('Iniciar sesión (determinista)', (WidgetTester tester) async {
    app.main();
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(ValueKey('campo_email')), const String.fromEnvironment('DOGFOOD_APP_EMAIL'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(ValueKey('campo_contrasena')), const String.fromEnvironment('DOGFOOD_APP_CONTRASENA'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(ValueKey('boton_entrar')));
    await tester.pumpAndSettle();
    for (var i = 0; i < 40 && find.text('Início').evaluate().isEmpty; i++) {
      await tester.pump(const Duration(milliseconds: 500));
    }
    expect(find.text('Início'), findsWidgets);
  });
}
