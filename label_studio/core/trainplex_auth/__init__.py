"""TrainPlex unified-auth bridge (Step 3.3).

Exposes the JWT-validating middleware and DRF authentication class that
let the fork accept TrainPlex (api.trainplex.in) access tokens via the
``Authorization: Bearer <jwt>`` header. Activated by setting
``TRAINPLEX_JWT_SECRET`` in the fork environment to the same value as
the TrainPlex backend's ``JWT_SECRET``. Falls through silently when
the header is missing so existing DRF Token + Session auth still works.
"""
