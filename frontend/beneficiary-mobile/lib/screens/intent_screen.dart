import 'package:flutter/material.dart';
import '../services/api.dart';
import 'receipt_screen.dart';

class IntentFlowScreen extends StatefulWidget{
  final Map<String,dynamic> beneficiary; final Map<String,dynamic> fps; final Map<String,dynamic> entitlement;
  const IntentFlowScreen({required this.beneficiary, required this.fps, required this.entitlement, super.key});
  @override State<IntentFlowScreen> createState()=>_I();
}
class _I extends State<IntentFlowScreen>{
  int step=1; String selectedDate='10 Sep'; int rice=12, wheat=8; String mode='SELF'; bool loading=false; String? error;
  @override void initState(){ super.initState(); rice= (widget.entitlement['remaining_rice_kg'] as int).clamp(0, widget.entitlement['rice_entitlement_kg'] as int); wheat= (widget.entitlement['remaining_wheat_kg'] as int).clamp(0, widget.entitlement['remaining_wheat_kg'] as int); }
  @override Widget build(BuildContext c){
    if(step==1) return Scaffold(appBar: AppBar(title: const Text('Plan My Collection')), body: SingleChildScrollView(padding: const EdgeInsets.all(14), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children:[
      Row(children:[_num(1,true), _line(), _num(2,false), _line(), _num(3,false)]),
      const Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children:[Text('Select', style: TextStyle(fontSize:10)), Text('Review', style: TextStyle(fontSize:10)), Text('Submit', style: TextStyle(fontSize:10))]),
      const SizedBox(height:12),
      const Text('Choose Collection Date', style: TextStyle(fontWeight: FontWeight.bold)), const SizedBox(height:6),
      Row(children:[
        for(var d in ['10 Sep (9-12)','11 Sep (9-12)','12 Sep (2-5)']) Expanded(child: GestureDetector(onTap: ()=>setState(()=>selectedDate=d), child: Container(margin: const EdgeInsets.only(right:6), padding: const EdgeInsets.all(10), decoration: BoxDecoration(border: Border.all(color: selectedDate==d?const Color(0xFF0F2A44):Colors.grey.shade300), borderRadius: BorderRadius.circular(8), color: selectedDate==d?const Color(0xFFEFF6FF):Colors.white), child: Column(children:[Text(d.split(' ')[0], style: const TextStyle(fontWeight: FontWeight.bold)), Text(d.split(' ').sublist(1).join(' '), style: const TextStyle(fontSize:10))])))),
      ]),
      const SizedBox(height:12),
      const Text('Choose FPS (if allowed)', style: TextStyle(fontWeight: FontWeight.bold)),
      ListTile(tileColor: Colors.white, shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8), side: BorderSide(color: Colors.grey.shade300)), leading: const Icon(Icons.store), title: Text(widget.fps['fps_name'] ?? widget.beneficiary['current_fps_id']), subtitle: Text(widget.fps['fps_id'] ?? ''), trailing: Container(padding: const EdgeInsets.symmetric(horizontal:6, vertical:2), decoration: BoxDecoration(color: const Color(0xFFDCFCE7), borderRadius: BorderRadius.circular(6)), child: const Text('Available', style: TextStyle(fontSize:10, color: Color(0xFF16A34A))))),
      const SizedBox(height:12),
      const Text('Select Quantity', style: TextStyle(fontWeight: FontWeight.bold)),
      _qty('Rice (kg)', rice, widget.entitlement['remaining_rice_kg'], widget.entitlement['rice_entitlement_kg'], (v)=>setState(()=>rice=v)),
      _qty('Wheat (kg)', wheat, widget.entitlement['remaining_wheat_kg'], widget.entitlement['wheat_entitlement_kg'], (v)=>setState(()=>wheat=v)),
      Container(padding: const EdgeInsets.all(8), decoration: BoxDecoration(color: const Color(0xFFFEF3C7), borderRadius: BorderRadius.circular(8)), child: Text('Remaining entitlement: Rice ${widget.entitlement['remaining_rice_kg']} kg, Wheat ${widget.entitlement['remaining_wheat_kg']} kg — Total requested ${rice+wheat} kg must be ≤ ${widget.entitlement['remaining_total_kg']} kg. Backend validates.', style: const TextStyle(fontSize:11, color: Color(0xFF92400E)))),
      const SizedBox(height:12),
      DropdownButtonFormField(value: mode, items: const [DropdownMenuItem(value:'SELF', child: Text('SELF')), DropdownMenuItem(value:'AUTHORIZED_PERSON', child: Text('Authorized Person'))], onChanged: (v)=>setState(()=>mode=v!), decoration: const InputDecoration(labelText:'Collection mode', border: OutlineInputBorder())),
      const SizedBox(height:16),
      SizedBox(width: double.infinity, child: ElevatedButton(style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF0F2A44), padding: const EdgeInsets.symmetric(vertical:14)), onPressed: ()=>setState(()=>step=2), child: const Text('Review & Submit', style: TextStyle(color: Colors.white)))),
    ])));
    // Step 2 Review
    return Scaffold(appBar: AppBar(title: const Text('Review Your Collection Plan')), body: Padding(padding: const EdgeInsets.all(16), child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children:[
      Container(padding: const EdgeInsets.all(12), decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(12)), child: Column(children:[
        _reviewRow('Cycle','September 2026'), _reviewRow('FPS', widget.fps['fps_name'] ?? widget.beneficiary['current_fps_id']), _reviewRow('Collection Date', selectedDate), _reviewRow('Rice', '$rice kg'), _reviewRow('Wheat', '$wheat kg'), _reviewRow('Total', '${rice+wheat} kg', bold:true), _reviewRow('Remaining after', '${(widget.entitlement['remaining_total_kg'] as int) - (rice+wheat)} kg'),
      ])),
      const SizedBox(height:8),
      Container(padding: const EdgeInsets.all(10), decoration: BoxDecoration(color: const Color(0xFFFEF3C7), borderRadius: BorderRadius.circular(8)), child: const Text('Please confirm before submitting. You cannot change your intent after the collection window closes.', style: TextStyle(fontSize:11, color: Color(0xFF92400E)))),
      if(error!=null) Padding(padding: const EdgeInsets.only(top:8), child: Text(error!, style: const TextStyle(color: Colors.red, fontSize:12))),
      const Spacer(),
      ElevatedButton(style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF0F2A44), padding: const EdgeInsets.symmetric(vertical:14)), onPressed: loading?null:() async {
        setState(()=>loading=true);
        try{
          final token = await ApiService.getToken();
          final r = await ApiService.submitIntent(token!, {'fps_id': widget.beneficiary['current_fps_id'], 'cycle':'2026-03','rice_quantity_kg':rice,'wheat_quantity_kg':wheat,'collection_mode':mode});
          if(!context.mounted) return;
          Navigator.pushReplacement(context, MaterialPageRoute(builder: (_)=> ReceiptScreen(receipt: r, fpsName: widget.fps['fps_name'] ?? widget.beneficiary['current_fps_id'])));
        }catch(e){ setState(()=>error=e.toString());}
        finally{ setState(()=>loading=false);}
      }, child: Text(loading?'Submitting...':'SUBMIT COLLECTION INTENT', style: const TextStyle(color: Colors.white))),
    ])));
  }
  Widget _num(int n, bool active)=> Container(width:28,height:28, decoration: BoxDecoration(color: active?const Color(0xFF0F2A44):Colors.grey.shade300, shape: BoxShape.circle), child: Center(child: Text('$n', style: TextStyle(color: active?Colors.white:Colors.black54, fontSize:12))));
  Widget _line()=> Expanded(child: Container(height:2, color: Colors.grey.shade300));
  Widget _qty(String label, int val, int remaining, int ent, Function(int) onCh)=> Card(child: Padding(padding: const EdgeInsets.all(10), child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children:[
    Column(crossAxisAlignment: CrossAxisAlignment.start, children:[Text(label, style: const TextStyle(fontWeight: FontWeight.bold, fontSize:12)), Text('Entitlement $ent kg · Remaining $remaining kg', style: const TextStyle(fontSize:10, color: Colors.black54))]),
    Row(children:[
      IconButton(onPressed: ()=> onCh((val-1).clamp(0, remaining)), icon: const Icon(Icons.remove_circle_outline)),
      Text('$val', style: const TextStyle(fontWeight: FontWeight.bold)),
      IconButton(onPressed: ()=> onCh((val+1).clamp(0, remaining)), icon: const Icon(Icons.add_circle_outline)),
    ])
  ])));
  Widget _reviewRow(String k, String v, {bool bold=false})=> Padding(padding: const EdgeInsets.symmetric(vertical:4), child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children:[Text(k, style: const TextStyle(fontSize:12, color: Colors.black54)), Text(v, style: TextStyle(fontWeight: bold?FontWeight.bold:FontWeight.w600, fontSize:12))] ));
}
