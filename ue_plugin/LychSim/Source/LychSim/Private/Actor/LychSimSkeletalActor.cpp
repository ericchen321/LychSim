#include "LychSimSkeletalActor.h"
#include "UObject/ConstructorHelpers.h"
#include "Components/StaticMeshComponent.h"
#include "UnrealcvLog.h"

ALychSimSkeletalActor::ALychSimSkeletalActor()
{
	PrimaryActorTick.bCanEverTick = true;

	Mesh = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("Mesh"));
	RootComponent = Mesh;
}

void ALychSimSkeletalActor::InitializeMesh(const FString& MeshPath)
{
	USkeletalMesh* Skeletal = LoadObject<USkeletalMesh>(nullptr, *MeshPath);
	if (Skeletal)
	{
        Mesh->SetSkeletalMesh(Skeletal);

        Mesh->SetCollisionProfileName(UCollisionProfile::PhysicsActor_ProfileName);
        Mesh->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
        Mesh->SetEnableGravity(true);

        // if (Mesh->GetPhysicsAsset())
        // {
        //     Mesh->SetSimulatePhysics(true);
        // }
	}
	else
	{
		UE_LOG(LogUnrealCV, Error, TEXT("Failed to load mesh from path: %s"), *MeshPath);
	}
}

void ALychSimSkeletalActor::BeginPlay()
{
    AActor::BeginPlay();
}

void ALychSimSkeletalActor::Tick(float DeltaTime)
{
	AActor::Tick(DeltaTime);
}
