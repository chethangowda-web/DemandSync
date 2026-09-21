import 'package:flutter/material.dart';
import '../services/api.dart';
import 'entitlement_screen.dart';
import 'intent_screen.dart';
import 'track_screen.dart';
import 'grievance_screen.dart';
import 'assistant_screen.dart';

class HomeScreen extends StatefulWidget {
  final Map<String,dynamic> beneficiary;
  final Map<String,dynamic> fps;
  final Map<String,dynamic> entitlement;
  final Map<String,dynamic> cycle;
  const HomeScreen({required this.beneficiary, required this.fps, required this.entitlement, required this.cycle, super.key});
  @override State<HomeScreen> createState()=>_H();
}
class _H extends State<HomeScreen>{
  int _idx=0;
  @override Widget build(BuildContext c){
    final ben = widget.beneficiary;
    final ent = widget.entitlement;
    final fps = widget.fps;
    return Scaffold(
      appBar: AppBar(backgroundColor: const Color(0xFF0F2A44), foregroundColor: Colors.white, title: const Text('DemandSYNC'), actions: [IconButton(onPressed: (){}, icon: const Icon(Icons.notifications_none))]),
      body: _idx==0 ? SingleChildScrollView(padding: const EdgeInsets.all(14), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children:[
        Container(width:double.infinity, padding: const EdgeInsets.all(14), decoration: BoxDecoration(color: const Color(0xFF0F2A44), borderRadius: BorderRadius.circular(12)), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children:[
          Text('Good Morning, ${ben['head_of_household']}', style: const TextStyle(color: Colors.white, fontSize:16, fontWeight: FontWeight.bold)),
          Text('Ration Card No: ${ben['ration_card_id']}', style: const TextStyle(color: Colors.white70, fontSize:11)),
          const SizedBox(height:10),
          Container(padding: const EdgeInsets.all(10), decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(8)), child: Column(children:[
            Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children:[
              const Text('Current Cycle', style: TextStyle(fontWeight: FontWeight.bold, fontSize:12)), Container(padding: const EdgeInsets.symmetric(horizontal:8, vertical:2), decoration: BoxDecoration(color: const Color(0xFF16A34A), borderRadius: BorderRadius.circular(10)), child: const Text('Active', style: TextStyle(color: Colors.white, fontSize:10))),
            ]),
            const SizedBox(height:4), Text('${widget.cycle['name'] ?? 'September 2026'}', style: const TextStyle(fontSize:14, fontWeight: FontWeight.w600)),
            const SizedBox(height:4), Text('Collection Window\n${widget.cycle['choice_window_start']} — ${widget.cycle['choice_window_end']}', style: const TextStyle(fontSize:11, color: Colors.black54)),
          ])),
        ])),
        const SizedBox(height:12),
        Container(padding: const EdgeInsets.all(12), decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(12), boxShadow:[BoxShadow(color: Colors.black.withOpacity(0.05), blurRadius:6)]), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children:[
          const Text('My Entitlement (Monthly)', style: TextStyle(fontWeight: FontWeight.bold, fontSize:13)),
          const SizedBox(height:8),
          Row(children:[
            Expanded(child: Column(children:[const Text('Rice', style: TextStyle(fontSize:11, color: Colors.black54)), Text('${ent['rice_entitlement_kg']} kg', style: const TextStyle(fontWeight: FontWeight.bold))])),
            Expanded(child: Column(children:[const Text('Wheat', style: TextStyle(fontSize:11, color: Colors.black54)), Text('${ent['wheat_entitlement_kg']} kg', style: const TextStyle(fontWeight: FontWeight.bold))])),
            Expanded(child: Column(children:[const Text('Total', style: TextStyle(fontSize:11, color: Colors.black54)), Text('${ent['total_entitlement_kg']} kg', style: const TextStyle(fontWeight: FontWeight.bold, color: Color(0xFF0F2A44)))])),
          ]),
          const Divider(),
          Row(children:[
            Expanded(child: Column(children:[const Text('Used', style: TextStyle(fontSize:11)), Text('${ent['used_total_kg']} kg', style: const TextStyle(fontWeight: FontWeight.bold))])),
            Expanded(child: Column(children:[const Text('Remaining', style: TextStyle(fontSize:11, color: Color(0xFF16A34A))), Text('${ent['remaining_total_kg']} kg', style: const TextStyle(fontWeight: FontWeight.bold, color: Color(0xFF16A34A)))])),
          ]),
        ])),
        const SizedBox(height:10),
        Container(padding: const EdgeInsets.all(12), decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(12)), child: Row(children:[
          Container(width:36,height:36,decoration:BoxDecoration(color: const Color(0xFFDCFCE7), borderRadius: BorderRadius.circular(8)), child: const Icon(Icons.check_circle, color: Color(0xFF16A34A))),
          const SizedBox(width:10), Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children:[
            const Text('Current Status', style: TextStyle(fontSize:11, color: Colors.black54)),
            Text('Collection Planned — FPS ${fps['fps_id'] ?? ben['current_fps_id']}', style: const TextStyle(fontSize:12, fontWeight: FontWeight.w600)),
          ])),
        ])),
        const SizedBox(height:12),
        SizedBox(width:double.infinity, child: ElevatedButton(style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF0F2A44), padding: const EdgeInsets.symmetric(vertical:14), shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8))), onPressed: ()=>Navigator.push(c, MaterialPageRoute(builder: (_)=> IntentFlowScreen(beneficiary: ben, fps: fps, entitlement: ent))), child: const Text('Plan My Collection', style: TextStyle(color: Colors.white)))),
        const SizedBox(height:8),
        SizedBox(width:double.infinity, child: OutlinedButton(onPressed: ()=>setState(()=>_idx=2), child: const Text('Track My Ration'))),
        const SizedBox(height:8),
        Container(padding: const EdgeInsets.all(10), decoration: BoxDecoration(color: const Color(0xFFFEF3C7), borderRadius: BorderRadius.circular(8)), child: const Row(children:[Icon(Icons.info, size:16, color: Color(0xFF92400E)), SizedBox(width:6), Expanded(child: Text('Your entitlement is based on your registered household and scheme. Rice + Wheat = Total. Statutory entitlement is read-only.', style: TextStyle(fontSize:11, color: Color(0xFF92400E))))])),
      ])) : _idx==1 ? EntitlementDetail(entitlement: ent, beneficiary: ben) : _idx==2 ? const TrackScreen() : _idx==3 ? const HistoryScreen() : const GrievanceScreen(),
      bottomNavigationBar: BottomNavigationBar(currentIndex: _idx, selectedItemColor: const Color(0xFF0F2A44), onTap: (i)=>setState(()=>_idx=i), items: const [
        BottomNavigationBarItem(icon: Icon(Icons.home), label: 'Home'),
        BottomNavigationBarItem(icon: Icon(Icons.card_giftcard), label: 'My Ration'),
        BottomNavigationBarItem(icon: Icon(Icons.local_shipping), label: 'Track'),
        BottomNavigationBarItem(icon: Icon(Icons.history), label: 'History'),
      ]),
      floatingActionButton: FloatingActionButton.small(onPressed: ()=>Navigator.push(c, MaterialPageRoute(builder: (_)=> const AssistantScreen())), backgroundColor: const Color(0xFF0F2A44), child: const Icon(Icons.smart_toy, color: Colors.white)),
    );
  }
}
class EntitlementDetail extends StatelessWidget {
  final Map<String,dynamic> entitlement; final Map<String,dynamic> beneficiary;
  const EntitlementDetail({required this.entitlement, required this.beneficiary, super.key});
  @override Widget build(BuildContext c){
    final e=entitlement;
    return SingleChildScrollView(padding: const EdgeInsets.all(14), child: Column(children:[
      Container(padding: const EdgeInsets.all(14), decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(12)), child: Column(children:[
        const Row(children:[Icon(Icons.verified, size:16, color: Color(0xFF16A34A)), SizedBox(width:6), Text('Monthly Entitlement (From Govt. Records)', style: TextStyle(fontWeight: FontWeight.bold, fontSize:12))]),
        const SizedBox(height:10),
        _row('Rice','${e['rice_entitlement_kg']} kg'), _row('Wheat','${e['wheat_entitlement_kg']} kg'), _row('Total','${e['total_entitlement_kg']} kg', bold:true),
        const Divider(),
        const Text('Usage This Cycle', style: TextStyle(fontWeight: FontWeight.bold, fontSize:12)),
        const SizedBox(height:6),
        Row(children:[Expanded(child: _smallCard('Used','${e['used_total_kg']} kg')), const SizedBox(width:8), Expanded(child: _smallCard('Remaining','${e['remaining_total_kg']} kg', green:true))]),
        const SizedBox(height:8),
        Container(padding: const EdgeInsets.all(8), decoration: BoxDecoration(color: const Color(0xFFEFF6FF), borderRadius: BorderRadius.circular(8)), child: const Text('Important: Your entitlement is based on your registered household and scheme information. Scheme: PHH/AAY — entitlement never modified by intent.', style: TextStyle(fontSize:11))),
      ])),
    ]));
  }
  Widget _row(String l, String v, {bool bold=false})=> Padding(padding: const EdgeInsets.symmetric(vertical:4), child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children:[Text(l, style: const TextStyle(fontSize:12)), Text(v, style: TextStyle(fontWeight: bold?FontWeight.bold:FontWeight.w600))] ));
  Widget _smallCard(String t, String v, {bool green=false})=> Container(padding: const EdgeInsets.all(10), decoration: BoxDecoration(color: green?const Color(0xFFDCFCE7):const Color(0xFFF1F5F9), borderRadius: BorderRadius.circular(8)), child: Column(children:[Text(t, style: const TextStyle(fontSize:11)), Text(v, style: TextStyle(fontWeight: FontWeight.bold, color: green?const Color(0xFF16A34A):Colors.black))] ));
}
class HistoryScreen extends StatelessWidget{ const HistoryScreen({super.key}); @override Widget build(BuildContext c)=> const Scaffold(body: Center(child: Text('History — real ePOS + intents from /history/me — if none: NO HISTORY AVAILABLE')));}
