import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:qr_flutter/qr_flutter.dart';

import '../core/api_client.dart';
import '../core/format.dart';
import '../core/labels.dart';
import '../core/models.dart';
import '../core/theme.dart';
import '../widgets/common.dart';

/// The e-PoS collection receipt, built by the backend from the recorded transaction.
class DigitalReceiptScreen extends StatelessWidget {
  const DigitalReceiptScreen({super.key, required this.transactionId});
  final String transactionId;

  @override
  Widget build(BuildContext context) {
    final l = tr(context);
    final loc = Localizations.localeOf(context).languageCode;
    final api = context.read<ApiClient>();
    return Scaffold(
      appBar: AppBar(title: Text(l.digitalReceipt)),
      body: AsyncBody<DigitalReceipt>(
        load: () => api.digitalReceipt(transactionId),
        builder: (context, r, reload) {
          final t = Theme.of(context).textTheme;
          return ListView(padding: const EdgeInsets.all(16), children: [
            SectionCard(
              child: Column(children: [
                Row(children: [
                  const CircleAvatar(backgroundColor: AppColors.goodSoft, child: Icon(Icons.verified_rounded, color: AppColors.good)),
                  const SizedBox(width: 12),
                  Expanded(child: Text(l.digitalReceipt, style: t.titleLarge)),
                  StatusChip(label: l.txnSuccess, tone: Tone.good, icon: Icons.check_circle_outline),
                ]),
                const Divider(height: 28),
                KeyValueRow(label: l.beneficiaryLabel, value: r.beneficiaryName),
                KeyValueRow(label: l.reviewCycle, value: cycleLabel(r.cycle, loc)),
                KeyValueRow(label: l.reviewFps, value: '${r.fpsName} (${r.fpsId})'),
                KeyValueRow(label: l.commodityLabel, value: commodityLabel(l, r.commodity)),
                KeyValueRow(label: l.quantityLabel, value: l.kgValue(kgText(r.quantityKg)), strong: true),
                KeyValueRow(label: l.dateTimeLabel, value: dateTimeText(r.time, loc)),
                KeyValueRow(label: l.transactionId, value: r.transactionId),
                KeyValueRow(label: l.receiptNumber, value: r.receiptNumber ?? l.dataUnavailable),
              ]),
            ),
            SectionCard(
              child: Column(children: [
                Semantics(
                  label: '${l.verificationRef}: ${r.verificationRef}',
                  child: Container(
                    color: Colors.white,
                    padding: const EdgeInsets.all(8),
                    child: QrImageView(data: r.qrPayload, size: 200, backgroundColor: Colors.white, semanticsLabel: '${l.verificationRef} ${r.verificationRef}'),
                  ),
                ),
                const SizedBox(height: 10),
                Text(l.verificationRef, style: t.bodyMedium?.copyWith(color: AppColors.textMuted)),
                SelectableText(r.verificationRef, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800, letterSpacing: 2)),
                const SizedBox(height: 8),
                Text(l.scanToVerify, textAlign: TextAlign.center, style: t.bodyMedium?.copyWith(color: AppColors.textMuted)),
              ]),
            ),
          ]);
        },
      ),
    );
  }
}
