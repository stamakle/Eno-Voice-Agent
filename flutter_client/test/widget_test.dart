import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:english_tech_flutter/main.dart';

void main() {
  testWidgets('app boots', (WidgetTester tester) async {
    await tester.pumpWidget(
      const EnglishTechApp(
        home: Scaffold(
          body: Text('english_tech test'),
        ),
      ),
    );
    expect(find.text('english_tech test'), findsOneWidget);
  });
}
