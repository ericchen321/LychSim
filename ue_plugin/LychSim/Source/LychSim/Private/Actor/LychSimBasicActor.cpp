#include "LychSimBasicActor.h"
#include "UObject/ConstructorHelpers.h"
#include "Components/StaticMeshComponent.h"
#include "UnrealcvLog.h"

ALychSimBasicActor::ALychSimBasicActor()
{
	PrimaryActorTick.bCanEverTick = true;

	Mesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Mesh"));
	RootComponent = Mesh;
}

void ALychSimBasicActor::InitializeMesh(const FString& MeshPath)
{
	UStaticMesh* LoadedMesh = LoadObject<UStaticMesh>(nullptr, *MeshPath);
	if (LoadedMesh)
	{
		Mesh->SetStaticMesh(LoadedMesh);

		Mesh->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
        Mesh->SetCollisionResponseToAllChannels(ECR_Block);
        Mesh->SetSimulatePhysics(true);
        Mesh->SetEnableGravity(true);
	}
	else
	{
		UE_LOG(LogUnrealCV, Error, TEXT("Failed to load mesh from path: %s"), *MeshPath);
	}
}

void ALychSimBasicActor::BeginPlay()
{
    AActor::BeginPlay();
}

void ALychSimBasicActor::Tick(float DeltaTime)
{
	AActor::Tick(DeltaTime);
}
