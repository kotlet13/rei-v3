# REI Fine-Tune Datasets

Datasets in this directory use the REI SFT dataset schema from
`app/backend/rei/ft_dataset.py`.

Generate the pilot dataset explicitly:

```powershell
python scripts\generate_rei_ft_dataset.py --dataset-id rei_ft_profile_pilot_v1 --model gemma4:26b --scenario-count 10 --confirm-run
```

The generator writes matched scenarios:

- 10 scenarios by default
- Racio, Emocio, and Instinkt example per scenario
- 13 EgoResultant examples per scenario, one per REI character profile, using the same processor signals
- `process_trace` inside every assistant payload
- SFT exports under `datasets/{dataset_id}/exports/`

Use validation before export:

```powershell
python scripts\validate_rei_ft_dataset.py rei_ft_profile_pilot_v1
python scripts\export_rei_ft_dataset.py rei_ft_profile_pilot_v1
```
