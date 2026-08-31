# AWS Cloud Cost Optimiser

A recommendation-based AWS cloud cost and utilisation analysis platform.

## Project Overview

AWS Cloud Cost Optimiser is a web-based, read-only platform that analyses
cloud cost, utilisation, and resource metadata to identify potential
cost-optimisation opportunities.

The system provides explainable recommendations with:

- Evidence
- Estimated savings
- Confidence level
- Risk level
- Human verification guidance

The system does not automatically modify AWS resources.

## Technology Stack

- React
- FastAPI
- PostgreSQL
- Python
- SQLAlchemy

## AWS Services Modelled

- EC2
- EBS
- S3

## Optimisation Rules

1. EC2 Low CPU
2. Unattached EBS
3. Idle Resource
4. Rapid S3 Growth

## Project Status

Currently in development.

## Architecture

Data → Analysis → Optimisation Rules → Recommendations → Dashboard