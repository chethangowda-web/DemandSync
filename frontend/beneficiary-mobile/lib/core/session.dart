import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Who is signed in, and which language they chose. The token is the only identity the app holds:
/// the backend decides who the beneficiary is from it, never from anything stored in the UI.
class SessionController extends ChangeNotifier {
  SessionController._(this._prefs, this._token, this._locale);

  /// In-memory session (tests, or when device storage is unavailable).
  factory SessionController.memory({String? token, Locale locale = const Locale('en')}) => SessionController._(null, token, locale);

  static const supportedLocales = [Locale('en'), Locale('hi'), Locale('kn')];
  static const _tokenKey = 'demandsync.token';
  static const _langKey = 'demandsync.lang';

  static Future<SessionController> load() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final lang = prefs.getString(_langKey);
      final locale = supportedLocales.firstWhere((l) => l.languageCode == lang, orElse: () => const Locale('en'));
      return SessionController._(prefs, prefs.getString(_tokenKey), locale);
    } catch (_) {
      return SessionController.memory();
    }
  }

  final SharedPreferences? _prefs;
  String? _token;
  Locale _locale;
  bool _expired = false;
  int _refresh = 0;

  String? get token => _token;
  bool get loggedIn => _token != null;
  Locale get locale => _locale;

  /// True when the last sign-out was forced by the server (expired or revoked session).
  bool get expired => _expired;

  /// Bumped after anything that changes server state, so visible screens reload.
  int get refreshTick => _refresh;

  Future<void> signIn(String token) async {
    _token = token;
    _expired = false;
    await _prefs?.setString(_tokenKey, token);
    notifyListeners();
  }

  Future<void> signOut() async {
    _token = null;
    _expired = false;
    await _prefs?.remove(_tokenKey);
    notifyListeners();
  }

  /// The server rejected the token. Clear it and tell the user why.
  void expire() {
    if (_token == null) return;
    _token = null;
    _expired = true;
    _prefs?.remove(_tokenKey);
    notifyListeners();
  }

  Future<void> setLocale(Locale locale) async {
    _locale = locale;
    await _prefs?.setString(_langKey, locale.languageCode);
    notifyListeners();
  }

  void bump() {
    _refresh++;
    notifyListeners();
  }
}
