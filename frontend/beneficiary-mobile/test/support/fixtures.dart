import 'dart:convert';
import 'dart:io';

import 'package:demandsync_beneficiary/core/api_exception.dart';

/// Responses recorded from the real backend (scripts/dump_beneficiary_fixtures.py).
Map<String, dynamic> fixture(String name) => jsonDecode(File('test/fixtures/$name.json').readAsStringSync()) as Map<String, dynamic>;

/// The ApiException the app would raise for a recorded backend error body.
ApiException recordedError(String name, int status) {
  final j = fixture(name);
  return ApiException(
    status >= 500 ? ApiErrorKind.server : ApiErrorKind.client,
    status: status,
    code: j['code'] as String?,
    message: (j['detail'] as String?) ?? '',
    params: Map<String, dynamic>.from((j['params'] as Map?) ?? const {}),
  );
}
