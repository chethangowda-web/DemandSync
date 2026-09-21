import 'package:flutter/material.dart';
class AssistantSheet extends StatelessWidget{
  const AssistantSheet({super.key});
  @override Widget build(BuildContext c){
    return Container(padding: const EdgeInsets.all(16), child: Column(mainAxisSize: MainAxisSize.min, children: const [
      Text('My PDS Assistant', style: TextStyle(fontWeight: FontWeight.bold)),
      SizedBox(height:8),
      Text('Ask: When to collect? How much left? What did I request? Has dispatch started? Where is FPS? Why not available?', style: TextStyle(fontSize:12)),
      SizedBox(height:8),
      Text('Answers use your authenticated data from PostgreSQL — AI explains, never changes entitlement or approves.', style: TextStyle(fontSize:11, color: Colors.black54)),
    ]));
  }
}
