import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api_client.dart';
import '../core/format.dart';
import '../core/labels.dart';
import '../core/models.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import 'digital_receipt_screen.dart';
import 'receipt_screen.dart';

/// Real records only. If there are none, it says so.
class HistoryScreen extends StatelessWidget {
  const HistoryScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final l = tr(context);
    final api = context.read<ApiClient>();
    return DefaultTabController(
      length: 3,
      child: Scaffold(
        appBar: AppBar(
          title: Text(l.historyTitle),
          actions: const [LanguageButton()],
          bottom: TabBar(
            indicatorColor: Colors.white,
            labelColor: Colors.white,
            unselectedLabelColor: const Color(0xFFB7C8EE),
            labelStyle: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15),
            tabs: [Tab(text: l.tabCollections), Tab(text: l.tabTransactions), Tab(text: l.tabIntents)],
          ),
        ),
        body: TabBarView(children: [
          AsyncBody<List<CollectionRecord>>(
              load: api.collections,
              builder: (c, items, reload) => _list(c, items.isEmpty, reload, [for (final r in items) _CollectionTile(record: r)],
                  icon: Icons.inventory_2_rounded, title: l.tabCollections)),
          AsyncBody<List<TransactionRecord>>(
              load: api.transactions,
              builder: (c, items, reload) => _list(c, items.isEmpty, reload, [for (final r in items) _TransactionTile(record: r)],
                  icon: Icons.receipt_long_rounded, title: l.tabTransactions)),
          AsyncBody<List<IntentRecord>>(
              load: api.intents,
              builder: (c, items, reload) => _list(c, items.isEmpty, reload, [for (final r in items) _IntentTile(record: r)],
                  icon: Icons.edit_calendar_rounded, title: l.tabIntents)),
        ]),
      ),
    );
  }

  Widget _list(BuildContext context, bool empty, Future<void> Function() reload, List<Widget> tiles, {required IconData icon, required String title}) {
    final l = tr(context);
    return RefreshIndicator(
      onRefresh: reload,
      child: empty
          ? ListView(children: [
              const SizedBox(height: 100),
              Center(child: IconBadge(icon: icon, color: AppColors.textMuted, size: 64, iconSize: 30)),
              const SizedBox(height: 14),
              Center(child: Text(l.noHistory, style: Theme.of(context).textTheme.titleMedium?.copyWith(color: AppColors.textMuted))),
            ])
          : ListView(padding: const EdgeInsets.all(16), children: [
              SectionHeader(icon: icon, title: title, subtitle: l.historySubtitle, badgeColor: AppColors.blue),
              const SizedBox(height: 14),
              ...tiles,
            ]),
    );
  }
}

class _CollectionTile extends StatelessWidget {
  const _CollectionTile({required this.record});
  final CollectionRecord record;

  @override
  Widget build(BuildContext context) {
    final l = tr(context);
    final loc = Localizations.localeOf(context).languageCode;
    final t = Theme.of(context).textTheme;
    return SectionCard(
      onTap: () => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => CollectionDetailScreen(record: record))),
      child: Row(children: [
        const IconBadge(icon: Icons.inventory_2_rounded, color: AppColors.good),
        const SizedBox(width: 14),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(cycleLabel(record.cycle, loc), style: t.titleMedium),
            Text(l.collectedDetail(kgText(record.riceKg), kgText(record.wheatKg)), style: t.bodyMedium),
            Text('${l.atShop(record.fpsName)} · ${dateText(record.at.toLocal(), loc)}', style: t.bodyMedium?.copyWith(color: AppColors.textMuted)),
          ]),
        ),
        Text(l.kgValue(kgText(record.totalKg)), style: t.titleMedium),
      ]),
    );
  }
}

class _TransactionTile extends StatelessWidget {
  const _TransactionTile({required this.record});
  final TransactionRecord record;

  @override
  Widget build(BuildContext context) {
    final l = tr(context);
    final loc = Localizations.localeOf(context).languageCode;
    final t = Theme.of(context).textTheme;
    final tone = switch (record.status) { 'SUCCESS' => Tone.good, 'FAILED' => Tone.bad, _ => Tone.neutral };
    return SectionCard(
      onTap: () {
        if (record.isSuccess) {
          Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => DigitalReceiptScreen(transactionId: record.reference)));
        } else {
          showMessage(context, l.noReceiptForFailed);
        }
      },
      child: Row(children: [
        IconBadge(icon: record.commodity == 'RICE' ? Icons.rice_bowl_rounded : Icons.grain_rounded, color: AppColors.blue),
        const SizedBox(width: 14),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('${commodityLabel(l, record.commodity)} · ${l.kgValue(kgText(record.quantityKg))}', style: t.titleMedium),
            Text('${cycleLabel(record.cycle, loc)} · ${dateTimeText(record.at, loc)}', style: t.bodyMedium?.copyWith(color: AppColors.textMuted)),
            Text(l.atShop(record.fpsName), style: t.bodyMedium?.copyWith(color: AppColors.textMuted)),
            if (record.receiptNumber != null) Text(record.receiptNumber!, style: t.bodyMedium?.copyWith(color: AppColors.textMuted)),
            const SizedBox(height: 6),
            StatusChip(label: txnStatusLabel(l, record.status), tone: tone, icon: record.isSuccess ? Icons.check_circle_outline : (record.status == 'FAILED' ? Icons.error_outline : Icons.cancel_outlined)),
          ]),
        ),
        if (record.isSuccess) const Icon(Icons.chevron_right_rounded, color: AppColors.textMuted),
      ]),
    );
  }
}

class _IntentTile extends StatefulWidget {
  const _IntentTile({required this.record});
  final IntentRecord record;

  @override
  State<_IntentTile> createState() => _IntentTileState();
}

class _IntentTileState extends State<_IntentTile> {
  bool _busy = false;

  Future<void> _open() async {
    final l = tr(context), api = context.read<ApiClient>();
    setState(() => _busy = true);
    try {
      final r = await api.intentReceipt(widget.record.reference);
      if (!mounted) return;
      Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => ReceiptScreen(receipt: r)));
    } catch (e) {
      if (mounted) showMessage(context, errorText(l, e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = tr(context);
    final loc = Localizations.localeOf(context).languageCode;
    final t = Theme.of(context).textTheme;
    final r = widget.record;
    final cancelled = r.status != 'RECORDED';
    return SectionCard(
      onTap: _busy ? null : _open,
      child: Row(children: [
        const IconBadge(icon: Icons.edit_calendar_rounded, color: AppColors.blue),
        const SizedBox(width: 14),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(cycleLabel(r.cycle, loc), style: t.titleMedium),
            Text(l.collectedDetail(kgText(r.riceKg), kgText(r.wheatKg)), style: t.bodyMedium),
            Text('${l.atShop(r.fpsName)} · ${dateText(r.at.toLocal(), loc)}', style: t.bodyMedium?.copyWith(color: AppColors.textMuted)),
            Text(r.reference, style: t.bodyMedium?.copyWith(color: AppColors.textMuted)),
            const SizedBox(height: 6),
            StatusChip(label: intentStatusLabel(l, r.status), tone: cancelled ? Tone.neutral : Tone.good, icon: cancelled ? Icons.cancel_outlined : Icons.check_circle_outline),
          ]),
        ),
        if (_busy) const SizedBox(width: 24, height: 24, child: CircularProgressIndicator(strokeWidth: 2.5)) else const Icon(Icons.chevron_right_rounded, color: AppColors.textMuted),
      ]),
    );
  }
}

/// The transactions that make up one collection, each with its digital receipt.
class CollectionDetailScreen extends StatelessWidget {
  const CollectionDetailScreen({super.key, required this.record});
  final CollectionRecord record;

  @override
  Widget build(BuildContext context) {
    final l = tr(context);
    final loc = Localizations.localeOf(context).languageCode;
    final api = context.read<ApiClient>();
    return Scaffold(
      appBar: AppBar(title: Text(cycleLabel(record.cycle, loc))),
      body: AsyncBody<List<TransactionRecord>>(
        load: api.transactions,
        builder: (context, all, reload) {
          final mine = all.where((t) => record.transactionIds.contains(t.reference)).toList();
          return ListView(padding: const EdgeInsets.all(16), children: [
            SectionHeader(icon: Icons.inventory_2_rounded, title: cycleLabel(record.cycle, loc), subtitle: l.atShop(record.fpsName), badgeColor: AppColors.good),
            const SizedBox(height: 14),
            SectionCard(
              child: Column(children: [
                KeyValueRow(label: l.rice, value: l.kgValue(kgText(record.riceKg))),
                KeyValueRow(label: l.wheat, value: l.kgValue(kgText(record.wheatKg))),
                KeyValueRow(label: l.total, value: l.kgValue(kgText(record.totalKg)), strong: true),
                KeyValueRow(label: l.reviewFps, value: record.fpsName),
                KeyValueRow(label: l.transactionsCount('${record.transactionIds.length}'), value: ''),
              ]),
            ),
            for (final t in mine) _TransactionTile(record: t),
          ]);
        },
      ),
    );
  }
}
