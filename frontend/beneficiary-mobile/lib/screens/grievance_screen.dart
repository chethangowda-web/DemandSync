import 'package:flutter/material.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../services/api.dart';
class GrievanceScreen extends StatefulWidget{ const GrievanceScreen({super.key}); @override State<GrievanceScreen> createState()=>_G();}
class _G extends State<GrievanceScreen>{
  String category='SHORT_DELIVERY'; final desc=TextEditingController(); bool loading=false; String? msg;
  @override Widget build(BuildContext c){
    return Scaffold(appBar: AppBar(title: const Text('Raise Grievance')), body: SingleChildScrollView(padding: const EdgeInsets.all(14), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children:[
      const Text('Tell us what happened. We will help you.', style: TextStyle(fontSize:12, color: Colors.black54)),
      const SizedBox(height:10),
      const Text('Select Issue Type', style: TextStyle(fontWeight: FontWeight.bold, fontSize:12)),
      ...['Short delivery','Wrong Quantity','FPS Issue','Quality Issue','Transaction Problem','Entitlement Question','Other'].map((e)=>RadioListTile(value: e.toUpperCase().replaceAll(' ','_'), groupValue: category, onChanged: (v)=>setState(()=>category=v!), title: Text(e, style: const TextStyle(fontSize:12)))),
      TextField(controller: desc, maxLines:4, maxLength:500, decoration: const InputDecoration(hintText:'Describe your issue in detail', border: OutlineInputBorder())),
      if(msg!=null) Padding(padding: const EdgeInsets.only(top:8), child: Text(msg!, style: const TextStyle(color: Color(0xFF16A34A), fontSize:12))),
      const SizedBox(height:10),
      SizedBox(width: double.infinity, child: ElevatedButton(style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF0F2A44), padding: const EdgeInsets.symmetric(vertical:14)), onPressed: loading?null:() async {
        setState(()=>loading=true);
        try{
          final t=await ApiService.getToken();
          // need fps id from me
          final me = await ApiService.me(t!);
          final fpsId = me['beneficiary']['current_fps_id'];
          final token = t;
          final r = await submitGrievance(token, fpsId, category, desc.text);
          setState(()=>msg='Grievance ${r['grievance_id']} recorded — AI triage will classify and route to officer');
        }catch(e){ setState(()=>msg=e.toString());}
        finally{ setState(()=>loading=false);}
      }, child: Text(loading?'Submitting...':'Submit Grievance', style: const TextStyle(color: Colors.white)))),
    ])));
  }
}
Future<Map<String,dynamic>> submitGrievance(String token, String fpsId, String cat, String d) async {
  final res = await http.post(Uri.parse('${ApiService.baseUrl}/api/v1/grievances'), headers:{'Authorization':'Bearer $token','Content-Type':'application/json'}, body: jsonEncode({'fps_id':fpsId,'category':cat,'description':d}));
  if(res.statusCode>=400) throw Exception(res.body);
  return jsonDecode(res.body);
}
