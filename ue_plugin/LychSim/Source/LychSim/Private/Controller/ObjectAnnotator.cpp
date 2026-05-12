// Weichao Qiu @ 2017
#include "Controller/ObjectAnnotator.h"
#include "Runtime/Engine/Public/EngineUtils.h"
#include "Runtime/Launch/Resources/Version.h"
#include "Component/AnnotationComponent.h"
#include "UnrealcvLog.h"
//add for part segmentation,for object traverse and scene compoents
#include "Runtime/Engine/Public/StaticMeshResources.h"
#include "UObject/UObjectIterator.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/MeshComponent.h"
// For UE4 < 17
// check https://github.com/unrealcv/unrealcv/blob/1369a72be8428547318d8a52ae2d63e1eb57a001/Source/UnrealCV/Private/Controller/ObjectAnnotator.cpp#L1

FObjectAnnotator::FObjectAnnotator()
{
}

/** Annotate all static mesh in the world */
void FObjectAnnotator::AnnotateWorld(UWorld* World)
{
	if (!IsValid(World))
	{
		UE_LOG(LogUnrealCV, Warning, TEXT("Can not annotate world, the world is not valid"));
		return;
	}

	TArray<AActor*> ActorArray;
	GetAnnotableActors(World, ActorArray);

	for (AActor* Actor : ActorArray)
	{
		FColor AnnotationColor = GetDefaultColor(Actor);

		if (!IsValid(Actor))
		{
			UE_LOG(LogUnrealCV, Warning, TEXT("Found invalid actor in AnnotateWorld"));
			continue;
		}
		// Use VertexColor as annotation
		this->SetAnnotationColor(Actor, AnnotationColor);
	}
	UE_LOG(LogUnrealCV, Log, TEXT("Annotate mesh of the scene (%d)"), AnnotationColors.Num());
}

void FObjectAnnotator::AnnotateWorldByElement(UWorld* World)
{
	if (!IsValid(World))
	{
		UE_LOG(LogUnrealCV, Warning, TEXT("Can not annotate world elements, the world is not valid"));
		return;
	}

	TArray<AActor*> ActorArray;
	GetAnnotableActors(World, ActorArray);

	for (AActor* Actor : ActorArray)
	{
		if (!IsValid(Actor))
		{
			UE_LOG(LogUnrealCV, Warning, TEXT("Found invalid actor when annotating elements"));
			continue;
		}

		TArray<UActorComponent*> MeshComponents = Actor->K2_GetComponentsByClass(UMeshComponent::StaticClass());
		if (MeshComponents.Num() == 0)
		{
			continue;
		}

		bool bRegisteredActorColor = false;

		for (UActorComponent* Component : MeshComponents)
		{
			if (UStaticMeshComponent* StaticMeshComponent = Cast<UStaticMeshComponent>(Component))
			{
				UStaticMesh* StaticMesh = StaticMeshComponent->GetStaticMesh();
				if (!IsValid(StaticMesh))
				{
					continue;
				}

				FStaticMeshRenderData* RenderData = StaticMesh->GetRenderData();
				if (!RenderData || RenderData->LODResources.Num() == 0)
				{
					continue;
				}

				const FStaticMeshLODResources& LODResource = RenderData->LODResources[0];
				const int32 NumSections = LODResource.Sections.Num();

				if (NumSections <= 0)
				{
					const FString PartId = BuildPartId(Actor->GetName(), StaticMeshComponent->GetName(), 0);
					const FColor PartColor = GetPartColor(PartId);
					CreateAnnotationComponentForMesh(StaticMeshComponent, PartColor, INDEX_NONE);
					if (!bRegisteredActorColor)
					{
						AnnotationColors.Emplace(Actor->GetName(), PartColor);
						bRegisteredActorColor = true;
					}
					continue;
				}

				for (int32 SectionIndex = 0; SectionIndex < NumSections; ++SectionIndex)
				{
					const FString PartId = BuildPartId(Actor->GetName(), StaticMeshComponent->GetName(), SectionIndex);
					const FColor PartColor = GetPartColor(PartId);
					CreateAnnotationComponentForMesh(StaticMeshComponent, PartColor, SectionIndex);
					if (!bRegisteredActorColor)
					{
						AnnotationColors.Emplace(Actor->GetName(), PartColor);
						bRegisteredActorColor = true;
					}
				}
				continue;
			}

			if (UMeshComponent* MeshComponent = Cast<UMeshComponent>(Component))
			{
				const FString PartId = BuildPartId(Actor->GetName(), MeshComponent->GetName(), 0);
				const FColor PartColor = GetPartColor(PartId);
				CreateAnnotationComponentForMesh(MeshComponent, PartColor, INDEX_NONE);
				if (!bRegisteredActorColor)
				{
					AnnotationColors.Emplace(Actor->GetName(), PartColor);
					bRegisteredActorColor = true;
				}
			}
		}
	}

	UE_LOG(LogUnrealCV, Log, TEXT("Annotate static mesh elements of the scene (%d parts)"), PartAnnotationColors.Num());
}

void FObjectAnnotator::AnnotateNewObjects(UWorld* World)
{
	if (!IsValid(World))
	{
		UE_LOG(LogUnrealCV, Warning, TEXT("Can not annotate world, the world is not valid"));
		return;
	}

	TArray<AActor*> ActorArray;
	GetAnnotableActors(World, ActorArray);

	uint32 Count = 0;
	for (AActor* Actor : ActorArray)
	{
		if (AnnotationColors.Contains(Actor->GetName()))
		{
			// Already annotated
			continue;
		}
		else
		{
			Count++;

			FColor AnnotationColor = GetDefaultColor(Actor);

			if (!IsValid(Actor))
			{
				UE_LOG(LogUnrealCV, Warning, TEXT("Found invalid actor in AnnotateWorld"));
				continue;
			}
			// Use VertexColor as annotation
			this->SetAnnotationColor(Actor, AnnotationColor);
		}
	}
	UE_LOG(LogUnrealCV, Log, TEXT("Annotate new mesh of the scene (%d)"), Count);
}

void FObjectAnnotator::SetAnnotationColor(AActor* Actor, const FColor& AnnotationColor)
{
	if (!IsValid(Actor))
	{
		return;
	}
	// CHECK: Add the annotation color regardless successful or not
	TArray<UActorComponent*> AnnotationComponents = Actor->K2_GetComponentsByClass(UAnnotationComponent::StaticClass());
	if (AnnotationComponents.Num() == 0)
	{
		CreateAnnotationComponent(Actor, AnnotationColor);
	}
	else
	{
		UpdateAnnotationComponent(Actor, AnnotationColor);
	}
	this->AnnotationColors.Emplace(Actor->GetName(), AnnotationColor);
	// TODO: Remote AnnotationColor Map!
}

void FObjectAnnotator::GetAnnotationColor(AActor* Actor, FColor& AnnotationColor)
{
	if (!IsValid(Actor))
	{
		UE_LOG(LogUnrealCV, Warning, TEXT("InActor is invalid in GetAnnotationColor"));
		return;
	}

	// FString ActorName = Actor->GetName();
	// if (!this->AnnotationColors.Contains(ActorName))
	// {
	// 	UE_LOG(LogUnrealCV, Warning, TEXT("Can not find actor %s in GetAnnotationColor"), *ActorName);
	// 	return;
	// }
	// AnnotationColor = this->AnnotationColors[ActorName];

	// Another way to get annotation color is directly read color from AnnotationComponent
	// TODO: Remove the first only leave the second method

	// Check its direct children, do not recursive, otherwise it is very easy to trigger the warning.
	TArray<UActorComponent*> AnnotationComponents = Actor->K2_GetComponentsByClass(UAnnotationComponent::StaticClass());
	TArray<UActorComponent*> MeshComponents = Actor->K2_GetComponentsByClass(UMeshComponent::StaticClass());
	// Note: Strange that the MeshComponents.Num() is twice the number of AnnotationComponents.Num()
	if (AnnotationComponents.Num() == 0) return;
	if (AnnotationComponents.Num() != MeshComponents.Num())
	{
		// UE_LOG(LogTemp, Warning, TEXT("More than one AnnotationComponent for MeshComponent."));
		UE_LOG(LogTemp, Warning, TEXT("In actor %s, the number of MeshComponent (%d) and AnnotationComponent (%d) is different."), *Actor->GetName(), MeshComponents.Num(), AnnotationComponents.Num());
		// for (UActorComponent* Component : MeshComponents)
		// {
		// 	UE_LOG(LogTemp, Warning, TEXT("%s"), *Component->GetName());
		// }
	}
	UAnnotationComponent* AnnotationComponent = Cast<UAnnotationComponent>(AnnotationComponents[0]);
	// check(AnnotationColor == AnnotationComponent->AnnotationColor);
	AnnotationColor = AnnotationComponent->GetAnnotationColor();
}

void FObjectAnnotator::GetAnnotableActors(UWorld* World, TArray<AActor*>& ActorArray)
{
	if (!IsValid(World))
	{
		UE_LOG(LogUnrealCV, Warning, TEXT("The world is invalid in GetAnnotableActors"));
		return;
	}

	for (TActorIterator<AActor> ActorItr(World); ActorItr; ++ActorItr)
	{
		AActor *Actor = *ActorItr;
		ActorArray.Add(Actor);
	}
}

UAnnotationComponent* FObjectAnnotator::CreateAnnotationComponentForMesh(UMeshComponent* MeshComponent, const FColor& AnnotationColor, int32 ElementIndex)
{
	if (!IsValid(MeshComponent))
	{
		return nullptr;
	}

	UAnnotationComponent* AnnotationComponent = NewObject<UAnnotationComponent>(MeshComponent);
	if (!IsValid(AnnotationComponent))
	{
		UE_LOG(LogUnrealCV, Warning, TEXT("Failed to create annotation component for mesh %s"), *MeshComponent->GetName());
		return nullptr;
	}

	if (ElementIndex >= 0)
	{
		AnnotationComponent->SetAllowedElement(ElementIndex);
	}
	else
	{
		AnnotationComponent->ClearAllowedElements();
	}

	AnnotationComponent->SetupAttachment(MeshComponent);
	AnnotationComponent->RegisterComponent();
	AnnotationComponent->SetAnnotationColor(AnnotationColor);
	AnnotationComponent->MarkRenderStateDirty();
	return AnnotationComponent;
}

/**
 * Debug tips:
 * AnnotationComponent->AnnotationColor = FColor::MakeRandomColor();
 */
void FObjectAnnotator::CreateAnnotationComponent(AActor* Actor, const FColor& AnnotationColor)
{
	// Two special type of actors
	// https://api.unrealengine.com/INT/API/Runtime/Landscape/ALandscape/index.html
	// https://api.unrealengine.com/INT/API/Runtime/Foliage/AInstancedFoliageActor/index.html
	if (!IsValid(Actor))
	{
		UE_LOG(LogUnrealCV, Warning, TEXT("Invalid actor in CreateAnnotationComponent"));
		return;
	}
	TArray<UActorComponent*> AnnotationComponents = Actor->K2_GetComponentsByClass(UAnnotationComponent::StaticClass());
	if (AnnotationComponents.Num() != 0)
	{
		UE_LOG(LogUnrealCV, Log, TEXT("Skip annotated actor %s"), *Actor->GetName());
		return;
	}

	TArray<UActorComponent*> MeshComponents = Actor->K2_GetComponentsByClass(UMeshComponent::StaticClass());
	if (MeshComponents.Num() > 0)
	{
		UE_LOG(LogTemp, Log, TEXT("Annotate actor %s (%s) with color %s"), *Actor->GetActorNameOrLabel(), *Actor->GetName(), *AnnotationColor.ToString());

		for (UActorComponent* Component : MeshComponents)
		{
			if (UMeshComponent* MeshComponent = Cast<UMeshComponent>(Component))
			{
				CreateAnnotationComponentForMesh(MeshComponent, AnnotationColor, INDEX_NONE);
			}
		}
	}
}


void FObjectAnnotator::UpdateAnnotationComponent(AActor* Actor, const FColor& AnnotationColor)
{
	if (!IsValid(Actor))
	{
		UE_LOG(LogUnrealCV, Warning, TEXT("Invalid actor in CreateAnnotationComponent"));
		return;
	}
	TArray<UActorComponent*> AnnotationComponents = Actor->K2_GetComponentsByClass(UAnnotationComponent::StaticClass());
	for (UActorComponent* Component : AnnotationComponents)
	{
		UAnnotationComponent* AnnotationComponent = Cast<UAnnotationComponent>(Component);
		AnnotationComponent->SetAnnotationColor(AnnotationColor);
		AnnotationComponent->MarkRenderStateDirty();
	}
}

FColor FObjectAnnotator::GetDefaultColor(AActor* Actor)
{
	FString ActorName = Actor->GetName();
	if (AnnotationColors.Contains(ActorName))
	{
		// Already initialized
		return AnnotationColors[ActorName];
	}

	int ColorIndex = AnnotationColors.Num();
	FColor AnnotationColor = ColorGenerator.GetColorFromColorMap(ColorIndex);

	return AnnotationColor;
}


/**
void FObjectAnnotator::AnnotateMeshComponents(UWorld* World)
{
	if (!IsValid(World))
	{
		UE_LOG(LogUnrealCV, Warning, TEXT("Can not annotate world, the world is not valid"));
		return;
	}

	// List all MeshComponents in the scene
	TArray<UMeshComponent*> ComponentList;
	TArray<UObject*> UObjectList;
	bool bIncludeDerivedClasses = true;
	EObjectFlags ExclusionFlags = EObjectFlags::RF_ClassDefaultObject;
	EInternalObjectFlags ExclusionInternalFlags = EInternalObjectFlags::AllFlags;
	GetObjectsOfClass(UMeshComponent::StaticClass(), UObjectList, bIncludeDerivedClasses, ExclusionFlags, ExclusionInternalFlags);
	for (UObject* Object : UObjectList)
	{
		UMeshComponent* Component = Cast<UMeshComponent>(Object);

		if (Component->GetWorld() == World
		&& !ComponentList.Contains(Component))
		{
			ComponentList.Add(Component);
		}
	}

	for (int i = 0; i < ComponentList.Num(); i++)
	// for (UMeshComponent* MeshComponent : ComponentList)
	{
		UMeshComponent* MeshComponent = ComponentList[i];
		if (!IsValid(MeshComponent))
		{
			UE_LOG(LogTemp, Warning, TEXT("MeshComponent is invalid."));
			continue;
		}

		UAnnotationComponent* AnnotationComponent = nullptr;
		TArray<USceneComponent*> AttachChildren = MeshComponent->GetAttachChildren();
		for (USceneComponent* Child : AttachChildren)
		{
			AnnotationComponent = Cast<UAnnotationComponent>(Child);
			if (IsValid(AnnotationComponent))
			{
				break;
			}
		}
		if (!IsValid(AnnotationComponent))
		{
			// Create a new one
			AnnotationComponent = NewObject<UAnnotationComponent>(MeshComponent);
			AnnotationComponent->SetupAttachment(MeshComponent);
			AnnotationComponent->RegisterComponent();
			AnnotationComponent->MarkRenderStateDirty();
		}
		// UE_LOG(LogTemp, Log, TEXT("Annotate %s with color %s"), *MeshComponent->GetName(), *AnnotationColor.ToString());
		// FColor AnnotationColor = FColor::MakeRandomColor();
		FColor AnnotationColor = ColorGenerator.GetColorFromColorMap(i);
		AnnotationComponent->SetAnnotationColor(AnnotationColor);
		// AnnotationComponent->AnnotationColor = FColor::MakeRandomColor(); // Debug
	}
}
*/

/** Utility function to generate color map */
int32 FColorGenerator::GetChannelValue(uint32 Index)
{
	static int32 Values[256] = { 0 };
	static bool Init = false;
	if (!Init)
	{
		float Step = 256;
		uint32 Iter = 0;
		Values[0] = 0;
		while (Step >= 1)
		{
			for (uint32 Value = Step - 1; Value <= 256; Value += Step * 2)
			{
				Iter++;
				Values[Iter] = Value;
			}
			Step /= 2;
		}
		Init = true;
	}
	if (Index >= 0 && Index <= 255)
	{
		return Values[Index];
	}
	else
	{
		UE_LOG(LogUnrealCV, Error, TEXT("Invalid channel index"));
		check(false);
		return -1;
	}
}

void FColorGenerator::GetColors(int32 MaxVal, bool Fix1, bool Fix2, bool Fix3, TArray<FColor>& ColorMap)
{
	for (int32 I = 0; I <= (Fix1 ? 0 : MaxVal - 1); I++)
	{
		for (int32 J = 0; J <= (Fix2 ? 0 : MaxVal - 1); J++)
		{
			for (int32 K = 0; K <= (Fix3 ? 0 : MaxVal - 1); K++)
			{
				uint8 R = (uint8)GetChannelValue(Fix1 ? MaxVal : I);
				uint8 G = (uint8)GetChannelValue(Fix2 ? MaxVal : J);
				uint8 B = (uint8)GetChannelValue(Fix3 ? MaxVal : K);
				FColor Color(R, G, B, 255);
				ColorMap.Add(Color);
			}
		}
	}
}

FColor FColorGenerator::GetColorFromColorMap(int32 ObjectIndex)
{
	static TArray<FColor> ColorMap;
	int NumPerChannel = 32;
	if (ColorMap.Num() == 0)
	{
		// 32 ^ 3
		for (int32 MaxChannelIndex = 0; MaxChannelIndex < NumPerChannel; MaxChannelIndex++) // Get color map for 1000 objects
		{
			// GetColors(MaxChannelIndex, false, false, false, ColorMap);
			GetColors(MaxChannelIndex, false, false, true, ColorMap);
			GetColors(MaxChannelIndex, false, true, false, ColorMap);
			GetColors(MaxChannelIndex, false, true, true, ColorMap);
			GetColors(MaxChannelIndex, true, false, false, ColorMap);
			GetColors(MaxChannelIndex, true, false, true, ColorMap);
			GetColors(MaxChannelIndex, true, true, false, ColorMap);
			GetColors(MaxChannelIndex, true, true, true, ColorMap);
		}
	}
	if (ObjectIndex < 0 || ObjectIndex >= pow(NumPerChannel, 3))
	{
		UE_LOG(LogUnrealCV, Error, TEXT("Object index %d is out of the color map boundary [%d, %d]"), ObjectIndex, 0, (int) pow(NumPerChannel, 3));
	}
	return ColorMap[ObjectIndex];
}

FColor FObjectAnnotator::GetPartColor(const FString& PartId)
{
	if (PartAnnotationColors.Contains(PartId))
	{
		return PartAnnotationColors[PartId];
	}

	int32 ColorIndex = PartAnnotationColors.Num();
	FColor PartColor = ColorGenerator.GetColorFromColorMap(ColorIndex);
	PartAnnotationColors.Add(PartId, PartColor);
	return PartColor;
}

FString FObjectAnnotator::BuildPartId(const FString& ActorName, const FString& ComponentName, int32 ElementIndex) const
{
	return FString::Printf(TEXT("%s_%s_%d"), *ActorName, *ComponentName, ElementIndex);
}


//Added for part segmentation, colored grouped actors with the same color
void FObjectAnnotator::AnnotateGroupedActors(UWorld* World)
{
    if (!IsValid(World)) return;
    TMap<AActor*, FColor> RootColor;
    for (TActorIterator<AActor> It(World); It; ++It)
	{
	    AActor* Actor = *It;
	    if (!IsValid(Actor)) continue;
	    // find top-level attachment root
	    AActor* Root = Actor;
	    while (Root->GetAttachParentActor())
		    Root = Root->GetAttachParentActor();
	    FColor* Existing = RootColor.Find(Root);
	    FColor Col;
	    if (Existing)
		{
	        Col = *Existing;
	    }
	    else
		{
		    Col = GetDefaultColor(Root);
		    RootColor.Add(Root, Col);
	    }
	    SetAnnotationColor(Actor, Col);
	    AnnotationColors.Emplace(Actor->GetName(), Col);
	}
	UE_LOG(LogUnrealCV, Log, TEXT("AnnotateGroupedActors: processed %d root groups"), RootColor.Num());
}


void FObjectAnnotator::ClearAnnotations(UWorld* World)
{
	if (!IsValid(World)) return;
	AnnotationColors.Empty();
	PartAnnotationColors.Empty();
	int32 Count = 0;
	for (TObjectIterator<UAnnotationComponent> It; It; ++It)
	{
	    UAnnotationComponent* Comp = *It;
	    if (!IsValid(Comp)) continue;
	    if (Comp->GetWorld() != World) continue;
	    Comp->DestroyComponent();
	    Count++;
	}
	UE_LOG(LogUnrealCV, Log, TEXT("ClearAnnotations: removed %d comps"), Count);
}
