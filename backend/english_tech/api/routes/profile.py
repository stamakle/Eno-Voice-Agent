from fastapi import APIRouter, Depends

from english_tech.auth.deps import get_verified_user
from english_tech.learners.models import LearnerProfile
from english_tech.learners.store import LearnerStore

router = APIRouter()
store = LearnerStore()


@router.get("/me")
def get_profile(user=Depends(get_verified_user)):
    return store.get_or_create_profile(user.learner_id).model_dump()


@router.post("/me")
def save_profile(profile: LearnerProfile, user=Depends(get_verified_user)):
    profile.learner_id = user.learner_id
    profile.display_name = user.display_name if not profile.display_name.strip() else profile.display_name
    store.save_profile(profile)
    return {"status": "saved", "learner_id": user.learner_id}
