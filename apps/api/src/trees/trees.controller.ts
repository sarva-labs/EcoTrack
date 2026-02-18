import { Controller, Get, Post, Body, Param, Query } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiResponse } from '@nestjs/swagger';
import { TreesService } from './trees.service';
import { CreateTreeDto } from './dto/create-tree.dto';

@ApiTags('trees')
@Controller('trees')
export class TreesController {
  constructor(private readonly treesService: TreesService) {}

  @Post()
  @ApiOperation({ summary: 'Create a new tree record' })
  @ApiResponse({ status: 201, description: 'Tree created successfully' })
  async create(@Body() createTreeDto: CreateTreeDto) {
    return this.treesService.create(createTreeDto);
  }

  @Get()
  @ApiOperation({ summary: 'Get all trees' })
  @ApiResponse({ status: 200, description: 'Returns all trees' })
  async findAll(@Query('limit') limit?: number, @Query('offset') offset?: number) {
    return this.treesService.findAll(limit, offset);
  }

  @Get(':id')
  @ApiOperation({ summary: 'Get tree by ID' })
  @ApiResponse({ status: 200, description: 'Returns a single tree' })
  @ApiResponse({ status: 404, description: 'Tree not found' })
  async findOne(@Param('id') id: string) {
    return this.treesService.findOne(id);
  }
}
