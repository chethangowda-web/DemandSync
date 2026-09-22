/// Why a call failed, in terms the UI can act on.
enum ApiErrorKind { offline, timeout, unauthorized, server, client }

class ApiException implements Exception {
  ApiException(this.kind, {this.status, this.code, this.message = '', this.params = const {}});

  final ApiErrorKind kind;
  final int? status;

  /// Stable machine-readable code from the backend (for example INTENT_DUPLICATE). The UI localises by this.
  final String? code;

  /// English fallback text from the backend. Shown only when the app has no localised text for [code].
  final String message;
  final Map<String, dynamic> params;

  bool get isSessionProblem => kind == ApiErrorKind.unauthorized;

  @override
  String toString() => 'ApiException($kind, $status, $code, $message)';
}
