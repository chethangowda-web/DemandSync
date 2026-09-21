import 'package:flutter/material.dart';
import '../services/api.dart';
class AssistantScreen extends StatefulWidget{ const AssistantScreen({super.key}); @override State<AssistantScreen> createState()=>_A();}
class _A extends State<AssistantScreen>{
  final ctrl=TextEditingController(); String? answer; String? source; bool loading=false;
  final chips=['How much entitlement left?','When to collect?','What did I request?','Has ration been dispatched?','Where is my FPS?'];
  Future<void> ask(String q) async {
    setState(()=>loading=true);
    final t=await ApiService.getToken();
    final r=await ApiService.assistant(t!, q);
    setState(()=>{answer=r['answer'], source=r['source'], loading=false});
  }
  @override Widget build(BuildContext c){
    return Scaffold(appBar: AppBar(title: const Text('My PDS Assistant')), body: Column(children:[
      Padding(padding: const EdgeInsets.all(12), child: Text('Ask about your ration, entitlement, collection status and more — AI explains your real records, never modifies entitlement.', style: TextStyle(fontSize:11, color: Colors.grey[600]))),
      if(answer!=null) Container(margin: const EdgeInsets.symmetric(horizontal:12), padding: const EdgeInsets.all(12), decoration: BoxDecoration(color: const Color(0xFFEFF6FF), borderRadius: BorderRadius.circular(12)), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children:[
        Text(answer!, style: const TextStyle(fontSize:13)),
        const SizedBox(height:6), Text('Source: $source', style: const TextStyle(fontSize:10, color: Colors.black54)),
        Text('AI explains, does not approve — authoritative data from PostgreSQL', style: TextStyle(fontSize:10, color: Colors.grey[600])),
      ])),
      const Spacer(),
      Wrap(spacing:6, children: chips.map((ch)=> ActionChip(label: Text(ch, style: const TextStyle(fontSize:11)), onPressed: ()=>ask(ch))).toList()),
      const SizedBox(height:8),
      Padding(padding: const EdgeInsets.all(12), child: Row(children:[
        Expanded(child: TextField(controller: ctrl, decoration: const InputDecoration(hintText:'Type your question...', border: OutlineInputBorder()))),
        const SizedBox(width:8), IconButton.filled(style: IconButton.styleFrom(backgroundColor: const Color(0xFF0F2A44)), onPressed: ()=>ask(ctrl.text), icon: loading? const SizedBox(width:16,height:16, child: CircularProgressIndicator(color: Colors.white, strokeWidth:2)): const Icon(Icons.send, color: Colors.white)),
      ])),
    ]));
  }
}
