// Weichao Qiu @ 2018
#include "UObjectUtils.h"
#include "Runtime/Engine/Public/EngineUtils.h"
#include "Runtime/CoreUObject/Public/UObject/UObjectIterator.h"

AActor* GetActorById(UWorld* World, FString ActorId)
{
	for (TActorIterator<AActor> ActorItr(World); ActorItr; ++ActorItr)
	{
		AActor* Actor = *ActorItr;
		if (Actor->GetWorld() == World && Actor->GetName() == ActorId)
		{
			return Actor;
		}
	}
	return nullptr;
}

UObject* GetObjectById(UWorld* World, FString ObjectId)
{
	for (TObjectIterator<UObject> ObjItr; ObjItr; ++ObjItr)
	{
		UObject* Obj = *ObjItr;
		if (Obj->GetWorld() == World && Obj->GetName() == ObjectId)
		{
			return Obj;
		}
	}
	return nullptr;
}

FString GetAssetPath(AActor* Actor)
{
	if (!Actor)
	{
		return TEXT("invalid_actor");
	}

	if (UStaticMeshComponent* SMC = Actor->FindComponentByClass<UStaticMeshComponent>())
	{
		if (UStaticMesh* StaticMesh = SMC->GetStaticMesh())
		{
			return StaticMesh->GetPathName();
		}
	}

	if (USkeletalMeshComponent* SkeletalMeshComp = Actor->FindComponentByClass<USkeletalMeshComponent>())
	{
		if (USkeletalMesh* SkeletalMesh = SkeletalMeshComp->SkeletalMesh)
		{
			return SkeletalMesh->GetPathName();
		}
	}

	if (UClass* ActorClass = Actor->GetClass())
	{
		return ActorClass->GetPathName();
	}

	return TEXT("unknown_asset_path");
}

void LockRotation(AActor* Actor)
{
	if (!Actor) return;

	UPrimitiveComponent* RootComp = Cast<UPrimitiveComponent>(Actor->GetRootComponent());
	if (RootComp && RootComp->IsSimulatingPhysics())
	{
		RootComp->SetSimulatePhysics(true);
		RootComp->BodyInstance.bLockXRotation = true;
		RootComp->BodyInstance.bLockYRotation = true;
		RootComp->BodyInstance.bLockZRotation = false;
		RootComp->BodyInstance.SetDOFLock(EDOFMode::SixDOF);

		RootComp->SetCollisionProfileName(TEXT("PhysicsActor"));
		RootComp->RecreatePhysicsState();

		RootComp->WakeAllRigidBodies();
	}
}
