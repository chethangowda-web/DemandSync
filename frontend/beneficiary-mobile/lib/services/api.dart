import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class ApiService {
  static const String baseUrl = String.fromEnvironment('API_BASE', defaultValue: 'http://10.0.2.2:8000');
  static Future<String?> getToken() async => (await SharedPreferences.getInstance()).getString('token');
  static Future<void> saveToken(String t) async => (await SharedPreferences.getInstance()).setString('token', t);

  static Future<Map<String,dynamic>> login(String rc, String mobile) async {
    final r = await http.post(Uri.parse('$baseUrl/api/v1/auth/beneficiary/request-otp'), headers:{'Content-Type':'application/json'}, body: jsonEncode({'ration_card_id':rc,'registered_mobile':mobile}));
    if(r.statusCode!=200) throw Exception(jsonDecode(r.body)['detail'] ?? r.body);
    return jsonDecode(r.body);
  }
  static Future<String> verifyOtp(String rc, String otp) async {
    final r = await http.post(Uri.parse('$baseUrl/api/v1/auth/beneficiary/verify-otp'), headers:{'Content-Type':'application/json'}, body: jsonEncode({'ration_card_id':rc,'otp':otp}));
    if(r.statusCode!=200) throw Exception('OTP failed');
    final j=jsonDecode(r.body); await saveToken(j['access_token']); return j['access_token'];
  }
  static Future<Map<String,dynamic>> me(String token) async {
    final r = await http.get(Uri.parse('$baseUrl/api/v1/beneficiaries/me'), headers:{'Authorization':'Bearer $token'});
    if(r.statusCode!=200) throw Exception('Unauthorized');
    return jsonDecode(r.body);
  }
  static Future<Map<String,dynamic>> entitlement(String t, String cycle) async {
    final r = await http.get(Uri.parse('$baseUrl/api/v1/beneficiaries/me/entitlement?cycle=$cycle'), headers:{'Authorization':'Bearer $t'});
    return jsonDecode(r.body);
  }
  static Future<Map<String,dynamic>> submitIntent(String t, Map body) async {
    final r = await http.post(Uri.parse('$baseUrl/api/v1/preferences'), headers:{'Authorization':'Bearer $t','Content-Type':'application/json'}, body: jsonEncode(body));
    if(r.statusCode==409) throw Exception('Your collection preference has already been submitted for this cycle.');
    if(r.statusCode!=200) throw Exception(jsonDecode(r.body)['detail'] ?? r.body);
    return jsonDecode(r.body);
  }
  static Future<Map<String,dynamic>> tracking(String t, String cycle) async {
    final r = await http.get(Uri.parse('$baseUrl/api/v1/tracking/me?cycle=$cycle'), headers:{'Authorization':'Bearer $t'});
    return jsonDecode(r.body);
  }
  static Future<Map<String,dynamic>> assistant(String t, String q) async {
    final r = await http.post(Uri.parse('$baseUrl/api/v1/ai/assistant'), headers:{'Authorization':'Bearer $t','Content-Type':'application/json'}, body: jsonEncode({'question':q}));
    return jsonDecode(r.body);
  }
}
