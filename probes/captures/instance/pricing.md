# Provisioned shape at list price — Frankfurt, 2026-08-26

Source: AWS Pricing API (`aws pricing get-products`, endpoint us-east-1), filtered
to `regionCode=eu-central-1`; 730 h/month. The shape is `infra/` as applied:
`t4g.small`, gp3 root 12 GB + data 20 GB, one Elastic IP in use.

| line | SKU / filter | rate | per month |
|---|---|---|---|
| instance | AmazonEC2 t4g.small, Linux, Shared, Used | $0.0192 / h | $14.02 |
| storage | AmazonEC2 `EUC1-EBS:VolumeUsage.gp3`, 32 GB | $0.0952 / GB-mo | $3.05 |
| public IPv4 | AmazonVPC `EUC1-PublicIPv4:InUseAddress` | $0.005 / h | $3.65 |
| Parameter Store (standard), Budgets (first two), S3 + CloudWatch at this volume | — | free tier / cents | ~$0–1 |
| **total, always on** | | | **≈ $20.7** |

Stopping the instance between working days removes the instance line for those
hours; the volume, the EIP (in use → idle, same $0.005/h either way now) and the
DNS stay. gp3 IOPS/throughput are inside the free baseline (3000 / 125 MB/s).
