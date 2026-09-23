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
          return ListView(padding: const EdgeInsets.all(16), children: [
            SectionCard(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                SectionHeader(
                  icon: Icons.verified_rounded,
                  title: l.digitalReceipt,
                  subtitle: l.digitalReceiptSubtitle,
                  badgeColor: AppColors.good,
                  trailing: StatusChip(label: l.txnSuccess, tone: Tone.good, icon: Icons.check_circle_outline),
                ),
                const Divider(height: 28),
                KeyValueRow(label: l.beneficiaryLabel, value: r.beneficiaryName),
                KeyValueRow(label: l.reviewCycle, value: cycleLabel(r.cycle, loc)),
                KeyValueRow(label: l.reviewFps, value: '${r.fpsName} (${r.fpsId})'),
                KeyValueRow(label: l.commodityLabel, value: commodityLabel(l, r.commodity)),
                const Divider(),
                Container(
                  decoration: BoxDecoration(color: AppColors.goodSoft, borderRadius: BorderRadius.circular(12)),
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                  child: KeyValueRow(label: l.quantityLabel, value: l.kgValue(kgText(r.quantityKg)), strong: true),
                ),
                const SizedBox(height: 8),
                KeyValueRow(label: l.dateTimeLabel, value: dateTimeText(r.time, loc)),
                KeyValueRow(label: l.transactionId, value: r.transactionId),
                KeyValueRow(label: l.receiptNumber, value: r.receiptNumber ?? l.dataUnavailable),
              ]),
            ),
            SectionCard(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                SectionHeader(icon: Icons.qr_code_2_rounded, title: l.verificationRef, subtitle: l.scanToVerify, badgeColor: AppColors.blue),
                const SizedBox(height: 14),
                Center(
                  child: Column(children: [
                    Semantics(
                      label: '${l.verificationRef}: ${r.verificationRef}',
                      child: Container(
                        decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(12), border: Border.all(color: AppColors.border)),
                        padding: const EdgeInsets.all(8),
                        child: QrImageView(data: r.qrPayload, size: 200, backgroundColor: Colors.white, semanticsLabel: '${l.verificationRef} ${r.verificationRef}'),
                      ),
                    ),
                    const SizedBox(height: 14),
                    SelectableText(r.verificationRef, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800, letterSpacing: 2, color: AppColors.navy)),
                  ]),
                ),
              ]),
            ),
          ]);
        },
      ),
    );
  }
}
