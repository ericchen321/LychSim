// Weichao Qiu @ 2017
#pragma once

#include "CoreMinimal.h"
#include "Runtime/Engine/Classes/GameFramework/Actor.h"

#include "ObjectAnnotator.h"
#include "PlayerViewMode.h"
#include "WorldController.generated.h"

UCLASS()
class AUnrealcvWorldController : public AActor
{
	GENERATED_BODY()

public:
	FObjectAnnotator ObjectAnnotator;

	UPROPERTY()
	UPlayerViewMode* PlayerViewMode;

	AUnrealcvWorldController(const FObjectInitializer& ObjectInitializer);

	virtual void BeginPlay() override;

	virtual void PostActorCreated() override;

	/** Open new level */
	void OpenLevel(FName LevelName);

	void InitWorld();

	void AttachPawnSensor();

	void Tick(float DeltaTime);

	/** Ensure annotation components exist before segmentation requests */
	void EnsureAnnotations();

	/** Force rebuild of annotations based on current segmentation mode */
	void RebuildAnnotations();

	void ClearAnnotations();

	bool IsAnnotationsReady();
	void AnnotateNewObjects();

	/** Update segmentation mode (part/object) used when generating annotations */
	void SetSegmentationMode(const FString& Mode);

	/** Mark annotations as dirty so they will be rebuilt on next request */
	void MarkAnnotationsDirty();

	FString GetSegmentationMode() const { return SegmentationMode; }

private:
	bool bAnnotationsReady;
	FString SegmentationMode;

	void ApplyAnnotations(UWorld* World);
};
