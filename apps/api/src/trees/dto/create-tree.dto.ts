import { IsString, IsNumber, IsOptional, IsObject, Min, Max } from 'class-validator';
import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';

export class CreateTreeDto {
  @ApiProperty({ description: 'Tree species name' })
  @IsString()
  species: string;

  @ApiProperty({ description: 'Latitude coordinate' })
  @IsNumber()
  @Min(-90)
  @Max(90)
  latitude: number;

  @ApiProperty({ description: 'Longitude coordinate' })
  @IsNumber()
  @Min(-180)
  @Max(180)
  longitude: number;

  @ApiPropertyOptional({ description: 'Estimated age in years' })
  @IsOptional()
  @IsNumber()
  @Min(0)
  estimated_age?: number;

  @ApiPropertyOptional({ description: 'Root spread in meters' })
  @IsOptional()
  @IsNumber()
  @Min(0)
  root_spread?: number;

  @ApiPropertyOptional({ description: 'Soil type' })
  @IsOptional()
  @IsString()
  soil_type?: string;

  @ApiPropertyOptional({ description: 'Tree height in meters' })
  @IsOptional()
  @IsNumber()
  @Min(0)
  height?: number;

  @ApiPropertyOptional({ description: 'Canopy diameter in meters' })
  @IsOptional()
  @IsNumber()
  @Min(0)
  canopy_diameter?: number;

  @ApiPropertyOptional({ description: 'Additional metadata' })
  @IsOptional()
  @IsObject()
  metadata?: Record<string, any>;
}
