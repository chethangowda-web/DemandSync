import 'package:flutter/material.dart';
class EntitlementScreen extends StatelessWidget {
  final Map<String,dynamic> data; const EntitlementScreen({required this.data, super.key});
  @override Widget build(BuildContext c){
    return Scaffold(appBar: AppBar(title: const Text('My Monthly Entitlement')), body: Padding(padding: const EdgeInsets.all(16), child: Column(children:[
      Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(children:[
        Text('Rice ${data['rice_entitlement_kg']} kg', style: const TextStyle(fontSize:18, fontWeight: FontWeight.bold)),
        Text('Wheat ${data['wheat_entitlement_kg']} kg', style: const TextStyle(fontSize:18, fontWeight: FontWeight.bold)),
        const Divider(),
        Text('Total ${data['entitlement_kg']} kg', style: const TextStyle(fontSize:20, fontWeight: FontWeight.bold)),
        Text('Used ${data['used'] ?? 0} kg · Remaining ${data['remaining'] ?? data['entitlement_kg']} kg (from successful ePOS)', style: const TextStyle(fontSize:12, color: Colors.black54)),
      ]))),
      const SizedBox(height:8), const Text('Your entitlement is based on your registered household and scheme. Never hardcoded 25kg.', style: TextStyle(fontSize:11, color: Colors.black54)),
    ])));
  }
}
