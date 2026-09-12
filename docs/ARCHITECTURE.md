# Scalable Ingestion Pipeline Architecture

![Architecture Diagram](file:///C:/Users/hp/.gemini/antigravity-ide/brain/e6a05fda-6f7d-45cb-9d9b-d985de20dd14/architecture_diagram_1789049922801.jpg)

## Overview
The pipeline is built around a **high-throughput message queue (Apache Kafka)** that decouples the **crawler/producer** layer from downstream processing. Multiple **parallel worker services** consume records, perform **deduplication**, **freshness validation**, and then persist data to **PostgreSQL** (metadata) and **Amazon S3** (raw content). A **dead-letter queue (DLQ)** captures unrecoverable failures for later analysis.

## Components
- **Message Queue (Kafka)** – Handles >500k records per day with partitioning for scalability and ordering guarantees per source.
- **Crawler / Producer** – Fetches source data, normalises payloads, and pushes messages to Kafka.
- **Worker Services** – Stateless services (containerised) that subscribe to Kafka topics, perform:
  - Idempotency & duplicate detection (SHA-256 payload hash).
  - Freshness gate (24-hour freshness check).
  - Content extraction & enrichment.
- **Deduplication Layer** – Shared Redis cache (or Kafka compacted topic) for quick duplicate look-ups.
- **Storage**
  - **PostgreSQL** – Stores structured metadata, provenance fields, and indexing for query.
  - **Amazon S3** – Stores raw HTML / PDF content blobs.
- **DLQ (Kafka dead-letter topic)** – Captures records that fail after retries, routed for manual inspection.
- **Monitoring & Observability** – Prometheus scrapes metrics from workers; Grafana dashboards visualise throughput, error rates, and lag.
- **Alerting** – Alertmanager notifies on high error rates, queue lag spikes, or storage failures.

## Data Flow
1. **Crawl** ? produce message with raw payload & source metadata.
2. **Kafka** ? distribute to worker partitions.
3. **Worker** ? deduplicate ? freshness check ? enrich.
4. **Store** ? write metadata to PostgreSQL, raw content to S3.
5. **Success** ? commit offset.
6. **Failure** ? retry policy ? on permanent failure ? send to DLQ.

## Scalability & Fault-Tolerance
- **Horizontal scaling** of workers by adding consumer instances.
- **Kafka replication** (3-way) ensures durability.
- **Stateless workers** allow rapid autoscaling.
- **Back-pressure** handled via Kafka consumer lag monitoring.
- **DLQ** enables safe handling of bad records without blocking the pipeline.

*All design elements are documentation-only; no code changes or deployments are performed in this phase.*

