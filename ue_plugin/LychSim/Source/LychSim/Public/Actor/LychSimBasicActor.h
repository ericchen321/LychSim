#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "LychSimBasicActor.generated.h"


UCLASS()
class LYCHSIM_API ALychSimBasicActor : public AActor
{
	GENERATED_BODY()

public:
	ALychSimBasicActor();

protected:
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaTime) override;

public:
    UFUNCTION(BlueprintCallable, Category = "LychSim")
    void InitializeMesh(const FString& MeshPath);

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Components")
    UStaticMeshComponent* Mesh;
};
