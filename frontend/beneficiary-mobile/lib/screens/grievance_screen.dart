import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api_client.dart';
import '../core/format.dart';
import '../core/labels.dart';
import '../core/models.dart';
import '../core/session.dart';
import '../core/theme.dart';
import '../widgets/common.dart';

const _categoryIcons = {
  'SHORT_DELIVERY': Icons.remove_shopping_cart_outlined,
  'WRONG_QUANTITY': Icons.scale_outlined,
  'FPS_ISSUE': Icons.storefront_outlined,
  'QUALITY': Icons.grain_rounded,
  'TRANSACTION_FAILURE': Icons.point_of_sale_rounded,
  'ENTITLEMENT_QUERY': Icons.help_outline_rounded,
  'COLLECTION_ISSUE': Icons.front_hand_outlined,
  'OTHER': Icons.more_horiz_rounded,
};

/// Raise a grievance. The assistant may suggest a category and related collections, but nothing is sent until the
/// beneficiary has chosen and pressed submit.
class GrievanceScreen extends StatefulWidget {
  const GrievanceScreen({super.key});

  @override
  State<GrievanceScreen> createState() => _GrievanceScreenState();
}

class _GrievanceScreenState extends State<GrievanceScreen> {
  final _text = TextEditingController();
  String? _category, _transactionId, _error;
  GrievanceSuggestion? _suggestion;
  bool _suggesting = false, _submitting = false;
  Grievance? _done;

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  bool get _ready => _category != null && _text.text.trim().length >= 10;

  Future<void> _suggest() async {
    final l = tr(context), api = context.read<ApiClient>();
    setState(() {
      _suggesting = true;
      _error = null;
    });
    try {
      final s = await api.suggestGrievance(_text.text.trim());
      if (mounted) setState(() => _suggestion = s);
    } catch (e) {
      if (mounted) setState(() => _error = errorText(l, e));
    } finally {
      if (mounted) setState(() => _suggesting = false);
    }
  }

  Future<void> _submit() async {
    final l = tr(context), api = context.read<ApiClient>(), session = context.read<SessionController>();
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      final g = await api.submitGrievance(category: _category!, description: _text.text.trim(), relatedTransactionId: _transactionId);
      session.bump();
      if (mounted) setState(() => _done = g);
    } catch (e) {
      if (mounted) setState(() => _error = errorText(l, e));
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = tr(context);
    final loc = Localizations.localeOf(context).languageCode;
    final t = Theme.of(context).textTheme;
    if (_done != null) {
      return Scaffold(
        appBar: AppBar(title: Text(l.grievanceTitle)),
        body: SafeArea(
          child: ListView(padding: const EdgeInsets.all(20), children: [
            const SizedBox(height: 20),
            const Center(child: CircleAvatar(radius: 40, backgroundColor: AppColors.goodSoft, child: Icon(Icons.check_rounded, size: 48, color: AppColors.good))),
            const SizedBox(height: 16),
            Semantics(header: true, liveRegion: true, child: Text(l.grievanceSubmitted, textAlign: TextAlign.center, style: t.headlineSmall)),
            const SizedBox(height: 8),
            Text(l.grievanceSubmittedBody, textAlign: TextAlign.center),
            const SizedBox(height: 18),
            SectionCard(child: Column(children: [KeyValueRow(label: l.referenceLabel, value: _done!.id, strong: true), KeyValueRow(label: l.grievanceTitle, value: categoryLabel(l, _done!.category))])),
            BigButton(label: l.myGrievances, icon: Icons.list_alt_rounded, onPressed: () => Navigator.of(context).pushReplacement(MaterialPageRoute<void>(builder: (_) => const MyGrievancesScreen()))),
            const SizedBox(height: 10),
            BigButton(label: l.done, style: BigButtonStyle.secondary, onPressed: () => Navigator.of(context).pop()),
          ]),
        ),
      );
    }
    return Scaffold(
      appBar: AppBar(title: Text(l.grievanceTitle)),
      body: SafeArea(
        child: Column(children: [
          Expanded(
            child: ListView(padding: const EdgeInsets.all(16), children: [
              Semantics(header: true, child: Text(l.chooseIssue, style: t.titleLarge)),
              const SizedBox(height: 10),
              Wrap(spacing: 8, runSpacing: 8, children: [
                for (final c in grievanceCategories)
                  ChoiceChip(
                    avatar: Icon(_categoryIcons[c], size: 20),
                    label: Text(categoryLabel(l, c), style: const TextStyle(fontSize: 15)),
                    selected: _category == c,
                    showCheckmark: true,
                    onSelected: (_) => setState(() => _category = c),
                    materialTapTargetSize: MaterialTapTargetSize.padded,
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 8),
                  ),
              ]),
              const SizedBox(height: 18),
              Semantics(header: true, child: Text(l.describeIssue, style: t.titleMedium)),
              const SizedBox(height: 8),
              TextField(controller: _text, maxLines: 5, minLines: 4, maxLength: 500, onChanged: (_) => setState(() {}), decoration: InputDecoration(hintText: l.describeHint, counterText: l.charCount('${_text.text.length}'))),
              BigButton(label: l.aiSuggest, icon: Icons.auto_awesome_outlined, style: BigButtonStyle.secondary, onPressed: _text.text.trim().length >= 5 ? _suggest : null, loading: _suggesting),
              if (_suggestion != null) ...[
                const SizedBox(height: 12),
                SectionCard(
                  tone: Tone.info,
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Row(children: [
                      const Icon(Icons.auto_awesome, color: AppColors.blue),
                      const SizedBox(width: 10),
                      Expanded(child: Text(l.aiSuggestion(categoryLabel(l, _suggestion!.category)), style: t.titleMedium)),
                    ]),
                    const SizedBox(height: 4),
                    Text(l.aiSuggestNote, style: t.bodyMedium?.copyWith(color: AppColors.textMuted)),
                    const SizedBox(height: 10),
                    BigButton(label: l.useSuggestion, style: BigButtonStyle.secondary, onPressed: () => setState(() => _category = _suggestion!.category)),
                    if (_suggestion!.related.isNotEmpty) ...[
                      const SizedBox(height: 14),
                      Text(l.aboutTransaction, style: t.titleMedium),
                      RadioGroup<String?>(
                        groupValue: _transactionId,
                        onChanged: (v) => setState(() => _transactionId = v),
                        child: Column(children: [
                          RadioListTile<String?>(value: null, title: Text(l.noTransactionLink), contentPadding: EdgeInsets.zero),
                          for (final tx in _suggestion!.related)
                            RadioListTile<String?>(
                              value: tx.id,
                              contentPadding: EdgeInsets.zero,
                              title: Text('${commodityLabel(l, tx.commodity)} · ${l.kgValue(kgText(tx.quantityKg))} · ${txnStatusLabel(l, tx.status)}'),
                              subtitle: Text('${cycleLabel(tx.cycle, loc)} · ${dateTimeText(tx.at, loc)}'),
                            ),
                        ]),
                      ),
                    ],
                  ]),
                ),
              ],
              if (_error != null) Padding(padding: const EdgeInsets.only(top: 12), child: Semantics(liveRegion: true, child: SectionCard(tone: Tone.bad, child: Text(_error!, style: const TextStyle(color: AppColors.bad, fontWeight: FontWeight.w600))))),
            ]),
          ),
          Container(
            padding: const EdgeInsets.fromLTRB(16, 10, 16, 12),
            decoration: const BoxDecoration(color: Colors.white, border: Border(top: BorderSide(color: AppColors.border))),
            child: BigButton(label: l.submitGrievance, icon: Icons.send_rounded, onPressed: _ready ? _submit : null, loading: _submitting),
          ),
        ]),
      ),
    );
  }
}

class MyGrievancesScreen extends StatelessWidget {
  const MyGrievancesScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final l = tr(context);
    final loc = Localizations.localeOf(context).languageCode;
    final api = context.read<ApiClient>();
    final t = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(title: Text(l.myGrievances)),
      body: AsyncBody<List<Grievance>>(
        load: api.myGrievances,
        builder: (context, items, reload) => RefreshIndicator(
          onRefresh: reload,
          child: items.isEmpty
              ? ListView(children: [const SizedBox(height: 120), Center(child: Text(l.noGrievances, style: t.titleMedium?.copyWith(color: AppColors.textMuted)))])
              : ListView(padding: const EdgeInsets.all(16), children: [
                  for (final g in items)
                    SectionCard(
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Row(children: [
                          Expanded(child: Text(categoryLabel(l, g.category), style: t.titleMedium)),
                          StatusChip(label: grievanceStatusLabel(l, g.status), tone: switch (g.status) { 'RESOLVED' || 'CLOSED' => Tone.good, 'IN_REVIEW' => Tone.info, _ => Tone.warn }, icon: g.status == 'RESOLVED' || g.status == 'CLOSED' ? Icons.check_circle_outline : Icons.hourglass_top_rounded),
                        ]),
                        const SizedBox(height: 6),
                        Text(g.description, maxLines: 3, overflow: TextOverflow.ellipsis),
                        const SizedBox(height: 6),
                        Text('${g.id} · ${dateText(g.createdAt.toLocal(), loc)}', style: t.bodyMedium?.copyWith(color: AppColors.textMuted)),
                        if (g.resolution != null && g.resolution!.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 6), child: Text('${l.resolutionLabel}: ${g.resolution}')),
                      ]),
                    ),
                ]),
        ),
      ),
    );
  }
}
