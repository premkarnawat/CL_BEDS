@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: DBSession):

    result = db.execute(
        text("SELECT id FROM users WHERE email = :email"),
        {"email": payload.email},
    )

    if result.fetchone():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user_id = uuid.uuid4()
    hashed = hash_password(payload.password)

    db.execute(
        text("""
            INSERT INTO users (id, email, full_name, role, password_hash, created_at)
            VALUES (:id, :email, :full_name, :role, :password_hash, :now)
        """),
        {
            "id": user_id,
            "email": payload.email,
            "full_name": payload.full_name,
            "role": payload.role.value,
            "password_hash": hashed,
            "now": datetime.now(tz=timezone.utc),
        },
    )

    return UserOut(
        id=user_id,
        email=payload.email,
        full_name=payload.full_name,
        role=payload.role,
    )
