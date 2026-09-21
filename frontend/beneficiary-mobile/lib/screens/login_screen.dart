import 'package:flutter/material.dart';
import '../services/api.dart';
class LoginScreen extends StatefulWidget{ const LoginScreen({super.key}); @override State<LoginScreen> createState()=>_L();}
class _L extends State<LoginScreen>{
  final rc=TextEditingController(text:'RC2023100000');
  final mobile=TextEditingController(text:'9000060000');
  final otp=TextEditingController();
  bool otpSent=false; bool loading=false; String? error;
  @override Widget build(BuildContext c){
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(gradient: LinearGradient(colors:[Color(0xFF0F2A44), Color(0xFF1E3A5F)], begin: Alignment.topCenter, end: Alignment.bottomCenter)),
        child: SafeArea(child: SingleChildScrollView(padding: const EdgeInsets.all(20), child: Column(children:[
          const SizedBox(height:30),
          Container(padding: const EdgeInsets.all(12), decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(16)), child: Column(children:[
            Container(width:56,height:56,decoration:BoxDecoration(color: const Color(0xFF0F2A44), borderRadius: BorderRadius.circular(12)), child: const Icon(Icons.agriculture, color: Colors.white, size:32)),
            const SizedBox(height:8), const Text('DemandSYNC', style: TextStyle(fontSize:22, fontWeight: FontWeight.bold, color: Color(0xFF0F2A44))), const Text('PDS PREDICT', style: TextStyle(fontSize:12, letterSpacing:2, color: Colors.black54)),
            const SizedBox(height:4), const Text('Welcome Back', style: TextStyle(fontSize:16, fontWeight: FontWeight.w600)), const Text('Please login to access your PDS services', style: TextStyle(fontSize:11, color: Colors.black54)),
            const SizedBox(height:16),
            TextField(controller: rc, decoration: const InputDecoration(labelText:'Ration Card Number', hintText:'RC2023100000', border: OutlineInputBorder(), prefixIcon: Icon(Icons.badge))), const SizedBox(height:10),
            TextField(controller: mobile, decoration: const InputDecoration(labelText:'Mobile Number', prefixText:'+91 ', border: OutlineInputBorder(), prefixIcon: Icon(Icons.phone)), keyboardType: TextInputType.phone),
            if(otpSent) Padding(padding: const EdgeInsets.only(top:10), child: TextField(controller: otp, decoration: const InputDecoration(labelText:'OTP Verification', hintText:'Enter 6 digit OTP', border: OutlineInputBorder()), keyboardType: TextInputType.number)),
            if(error!=null) Padding(padding: const EdgeInsets.only(top:8), child: Text(error!, style: const TextStyle(color: Colors.red, fontSize:12))),
            const SizedBox(height:12),
            SizedBox(width:double.infinity, child: ElevatedButton(
              style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF0F2A44), padding: const EdgeInsets.symmetric(vertical:14), shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8))),
              onPressed: loading?null:() async {
                setState(()=>loading=true);
                try{
                  if(!otpSent){
                    final r=await ApiService.login(rc.text.trim(), mobile.text.trim());
                    setState(()=>otpSent=true);
                    if(!context.mounted) return;
                    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('DEV OTP: ${r['dev_otp']} — ${r['note']}'), duration: const Duration(seconds:4)));
                  } else {
                    await ApiService.verifyOtp(rc.text.trim(), otp.text.trim());
                    if(!context.mounted) return;
                    Navigator.pushReplacementNamed(context, '/home');
                  }
                }catch(e){ setState(()=>error=e.toString());}
                finally{ setState(()=>loading=false);}
              },
              child: Text(otpSent?'Verify & Continue':'Send OTP', style: const TextStyle(color: Colors.white)),
            )),
            if(otpSent) TextButton(onPressed: ()=>setState(()=>error='DEV MODE: OTP is 123456'), child: const Text('Resend OTP (DEV: 123456)', style: TextStyle(fontSize:11))),
            const SizedBox(height:8), const Text('Need Help? Contact Support', style: TextStyle(fontSize:11, color: Colors.black54)),
          ])),
          const SizedBox(height:16),
          const Row(mainAxisAlignment: MainAxisAlignment.spaceEvenly, children:[
            Column(children:[Icon(Icons.verified, color: Colors.white70), SizedBox(height:4), Text('Transparent Process', style: TextStyle(color: Colors.white70, fontSize:10))]),
            Column(children:[Icon(Icons.update, color: Colors.white70), SizedBox(height:4), Text('Real-time Updates', style: TextStyle(color: Colors.white70, fontSize:10))]),
            Column(children:[Icon(Icons.auto_awesome, color: Colors.white70), SizedBox(height:4), Text('AI Powered Assistance', style: TextStyle(color: Colors.white70, fontSize:10))]),
          ]),
        ]))),
      ),
    );
  }
}
