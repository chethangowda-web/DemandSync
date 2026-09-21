import 'package:flutter/material.dart';
class ReceiptScreen extends StatelessWidget{
  final Map<String,dynamic> receipt; final String fpsName;
  const ReceiptScreen({required this.receipt, required this.fpsName, super.key});
  @override Widget build(BuildContext c){
    return Scaffold(appBar: AppBar(title: const Text('Intent Receipt')), body: SingleChildScrollView(padding: const EdgeInsets.all(16), child: Column(children:[
      const Icon(Icons.check_circle, color: Color(0xFF16A34A), size:64),
      const SizedBox(height:8), const Text('Collection Intent Recorded', style: TextStyle(fontSize:18, fontWeight: FontWeight.bold)),
      const Text('Your collection intent has been successfully submitted.', style: TextStyle(fontSize:12, color: Colors.black54)),
      const SizedBox(height:16),
      Container(padding: const EdgeInsets.all(14), decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(12), border: Border.all(color: Colors.grey.shade200)), child: Column(children:[
        _row('Cycle','September 2026'), _row('Rice','${receipt['rice_quantity_kg']} kg'), _row('Wheat','${receipt['wheat_quantity_kg']} kg'), _row('Total','${receipt['total_quantity_kg']} kg', bold:true),
        _row('FPS', fpsName), _row('Reference No', receipt['reference'] ?? receipt['intent_id']), _row('Submitted On', receipt['submitted_at'] ?? ''), _row('Status','Recorded', green:true),
      ])),
      const SizedBox(height:12),
      SizedBox(width: double.infinity, child: ElevatedButton(style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF0F2A44)), onPressed: (){}, child: const Text('View Details', style: TextStyle(color: Colors.white)))),
      const SizedBox(height:8),
      SizedBox(width: double.infinity, child: OutlinedButton(onPressed: ()=>Navigator.pop(c), child: const Text('Track My Ration'))),
      const SizedBox(height:8), const Text('Receipt generated from backend POST /preferences — reference is authoritative.', style: TextStyle(fontSize:11, color: Colors.black54)),
    ])));
  }
  Widget _row(String k, String v, {bool bold=false, bool green=false})=> Padding(padding: const EdgeInsets.symmetric(vertical:4), child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children:[Text(k, style: const TextStyle(fontSize:12, color: Colors.black54)), Text(v, style: TextStyle(fontSize:12, fontWeight: bold||green?FontWeight.bold:FontWeight.w600, color: green?const Color(0xFF16A34A):Colors.black))] ));
}
