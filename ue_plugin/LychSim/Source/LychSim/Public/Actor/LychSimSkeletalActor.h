#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "LychSimSkeletalActor.generated.h"


UCLASS()
class LYCHSIM_API ALychSimSkeletalActor : public AActor
{
	GENERATED_BODY()

public:
	ALychSimSkeletalActor();

protected:
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaTime) override;

public:
    UFUNCTION(BlueprintCallable, Category = "LychSim")
    void InitializeMesh(const FString& MeshPath);

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
    USkeletalMeshComponent* Mesh;
};
