import 'package:intl/intl.dart';

/// kg values arrive as whole numbers or decimals. Whole numbers are shown without a trailing ".0".
String kgText(num v) => v == v.roundToDouble() ? v.toInt().toString() : v.toStringAsFixed(1);

/// "2026-03" -> "March 2026" in the user's language.
String cycleLabel(String cycle, String locale) {
  final y = int.parse(cycle.substring(0, 4)), m = int.parse(cycle.substring(5, 7));
  return DateFormat.yMMMM(locale).format(DateTime(y, m));
}

String dateText(DateTime d, String locale) => DateFormat.yMMMd(locale).format(d);

String dateTimeText(DateTime d, String locale) => DateFormat.yMMMd(locale).add_jm().format(d.toLocal());

String shortDate(DateTime d, String locale) => DateFormat.MMMd(locale).format(d);

/// Ration card numbers are personal; show only the tail on shared surfaces.
String maskedCard(String id) => id.length <= 4 ? id : '••••${id.substring(id.length - 4)}';
