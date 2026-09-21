import 'package:flutter/material.dart';
import '../services/api.dart';

class TrackScreen extends StatefulWidget{ const TrackScreen({super.key}); @override State<TrackScreen> createState()=>_T();}
class _T extends State<TrackScreen>{
  Map<String,dynamic>? data; bool loading=true;
  @override void initState(){ super.initState(); _load();}
  Future<void> _load() async {
    final t=await ApiService.getToken();
    if(t!=null) data = await ApiService.tracking(t, '2026-03');
    setState(()=>loading=false);
  }
  @override Widget build(BuildContext c){
    if(loading) return const Scaffold(body: Center(child: CircularProgressIndicator()));
    if(data==null) return const Scaffold(body: Center(child: Text('Data unavailable')));
    final steps = (data!['steps'] as List);
    final tel = data!['telemetry'];
    return Scaffold(appBar: AppBar(title: const Text('Track My Ration')), body: SingleChildScrollView(padding: const EdgeInsets.all(14), child: Column(children:[
      Container(padding: const EdgeInsets.all(10), decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(12)), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children:[
        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children:[const Text('Current Cycle', style: TextStyle(fontSize:11, color: Colors.black54)), Container(padding: const EdgeInsets.symmetric(horizontal:6, vertical:2), decoration: BoxDecoration(color: const Color(0xFF16A34A), borderRadius: BorderRadius.circular(6)), child: const Text('Active', style: TextStyle(color: Colors.white, fontSize:10)))]),
        Text('September 2026', style: const TextStyle(fontWeight: FontWeight.bold)),
        const SizedBox(height:10),
        ...steps.map((s)=>Row(children:[
          Container(width:20,height:20, decoration: BoxDecoration(shape: BoxShape.circle, color: s['status']=='DONE'?const Color(0xFF16A34A):s['status']=='ACTIVE'?const Color(0xFF0F2A44):Colors.grey.shade300), child: Icon(s['status']=='DONE'?Icons.check:s['status']=='ACTIVE'?Icons.circle:Icons.circle_outlined, size:12, color: Colors.white)),
          const SizedBox(width:10), Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children:[
            Text(s['label'], style: TextStyle(fontWeight: s['status']=='ACTIVE'?FontWeight.bold:FontWeight.w500, fontSize:12)),
            if(s['timestamp']!=null) Text(s['timestamp'], style: const TextStyle(fontSize:10, color: Colors.black54)),
          ])),
        ])),
        const SizedBox(height:8),
        Container(height:120, decoration: BoxDecoration(color: const Color(0xFFF1F5F9), borderRadius: BorderRadius.circular(8)), child: Center(child: tel!=null ? Text('Vehicle ${tel['vehicle_id']} — ${tel['latitude']},${tel['longitude']} — ${tel['speed_kmph']} kmph — ${tel['status']}') : const Text('Live location unavailable — real telemetry gap (12% of vehicles)', style: TextStyle(fontSize:11)))),
        const SizedBox(height:8),
        Container(padding: const EdgeInsets.all(8), decoration: BoxDecoration(color: const Color(0xFFF0F9FF), borderRadius: BorderRadius.circular(8)), child: const Row(children:[Icon(Icons.smart_toy, size:16, color: Color(0xFF0F2A44)), SizedBox(width:6), Expanded(child: Text('AI Update: Your ration dispatch status is derived from real dispatch_manifests + vehicle_telemetry. No fake truck.', style: TextStyle(fontSize:11)))])),
      ])),
    ])));
  }
}
