import 'package:flutter/material.dart';
import 'screens/login_screen.dart';
import 'screens/home_screen.dart';
import 'services/api.dart';

void main() => runApp(const DemandSyncApp());

class DemandSyncApp extends StatelessWidget {
  const DemandSyncApp({super.key});
  @override Widget build(BuildContext c){
    return MaterialApp(
      title: 'DemandSYNC',
      theme: ThemeData(
        primaryColor: const Color(0xFF0F2A44),
        scaffoldBackgroundColor: const Color(0xFFF8FAFC),
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF0F2A44)),
        useMaterial3: true,
      ),
      home: const LoginScreen(),
      routes: {
        '/home': (c)=> const HomeScreenWrapper(),
      },
    );
  }
}
class HomeScreenWrapper extends StatefulWidget{ const HomeScreenWrapper({super.key}); @override State<HomeScreenWrapper> createState()=>_H();}
class _H extends State<HomeScreenWrapper>{
  String? token; Map<String,dynamic>? ben; Map<String,dynamic>? ent;
  @override void initState(){ super.initState(); loaded=false; _load();}
  bool loaded=false;
  Future<void> _load() async {
    final t = await ApiService.getToken();
    if(t==null) return;
    token=t;
    ben = await ApiService.me(token!);
    ent = await ApiService.entitlement(token!, '2026-03');
    setState(()=>loaded=true);
  }
  @override Widget build(BuildContext c){
    if(!loaded) return const Scaffold(body: Center(child: CircularProgressIndicator()));
    // Pass real data — no mockBeneficiary
    return HomeScreen(beneficiary: ben!['beneficiary'], fps: ben!['fps'], entitlement: ent!, cycle: {'cycle':'2026-03','name':'September 2026','choice_window_start':'2026-03-05','choice_window_end':'2026-03-20'});
  }
}
